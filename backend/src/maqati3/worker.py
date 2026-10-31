"""The worker: a second process of the same codebase, claiming jobs from the queue.

One kind so far, `transcribe`. The loop is deliberately small -- `work_once` claims a
job, runs it, and writes the result of that attempt back to the queue -- because every
interesting decision is about what happens when a run leaves nothing behind:

* **Nothing to send** (the staged file is gone) and **the provider failed**: retry with
  backoff. Nothing was stored and nothing was charged for a result we do not have.
* **No words at all**: terminal. The same audio will be just as silent on the next
  attempt, and four more attempts would be four more bills. The job row keeps the
  reason, and an admin may ask again once the file is replaced.
* **A transcript appeared while this run was in flight**: the job is done, not retried.
  Another worker won, or a reviewer typed it in; either way our result is thrown away
  rather than written over theirs.

A transcription outlives a sane lease, so the lease is held open by a heartbeat thread
while the provider works (`db.queue.heartbeat`). Without it the lease lapses mid-run,
the job is handed to a second worker, and the same recording is transcribed twice.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from maqati3.asr import AsrError, Transcriber
from maqati3.db.queue import Dead, Job, LeaseLost, Retry, claim, complete, fail, heartbeat
from maqati3.db.sql import Executor
from maqati3.domain import Lang
from maqati3.transcription import JOB_KIND, AlreadyTranscribed, EmptyTranscript, Transcripts

log = logging.getLogger("maqati3")

#: How long a claim is held before the lease has to be renewed. Short enough that a
#: worker killed mid-run frees the job quickly; the heartbeat keeps a live run safe.
LEASE_SECONDS = 300

#: Renewed well before the lease runs out, so one slow renewal does not lose it.
HEARTBEAT_SECONDS = LEASE_SECONDS // 3

#: How long the worker waits when the queue is empty.
IDLE_SLEEP_S = 5.0


class MediaMissing(Exception):
    """The file the entry was registered from is not where the database says it is."""


@dataclass(frozen=True, slots=True)
class Stored:
    """The run finished and its draft is in front of a reviewer."""

    entry_id: str
    lines: int


@dataclass(frozen=True, slots=True)
class Skipped:
    """The run finished but its result was not needed any more."""

    entry_id: str
    reason: str


Outcome = Stored | Skipped | Retry | Dead | LeaseLost


def run_transcription(
    payload: dict[str, Any], *, transcriber: Transcriber, transcripts: Transcripts
) -> Stored | Skipped:
    """One transcription, end to end. Raises for everything the queue should retry."""
    entry_id = str(payload["entry_id"])
    lang = Lang(str(payload.get("lang", Lang.AR.value)))
    path = transcripts.media_path(entry_id)
    if path is None:
        raise MediaMissing(entry_id)
    transcript = transcriber.transcribe(path, lang=lang)
    try:
        lines = transcripts.store(entry_id, transcript)
    except AlreadyTranscribed:
        log.info("transcript for %s arrived too late; dropping it", entry_id)
        return Skipped(entry_id=entry_id, reason="already_transcribed")
    return Stored(entry_id=entry_id, lines=lines)


class _Heartbeat:
    """Renews a job's lease in the background while the run takes its time."""

    def __init__(self, executor: Executor, job: Job) -> None:
        self._executor = executor
        self._job = job
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._beat, daemon=True)

    def __enter__(self) -> _Heartbeat:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _beat(self) -> None:
        while not self._stop.wait(HEARTBEAT_SECONDS):
            if not heartbeat(self._executor, self._job, LEASE_SECONDS):
                log.warning("lease on job %d was lost while it was running", self._job.id)
                return


def work_once(
    executor: Executor,
    *,
    transcriber: Transcriber,
    transcripts: Transcripts,
    lease_seconds: int = LEASE_SECONDS,
) -> Outcome | None:
    """Claim one transcription job and run it. None means the queue was empty."""
    job = claim(executor, [JOB_KIND], lease_seconds)
    if job is None:
        return None
    try:
        with _Heartbeat(executor, job):
            outcome = run_transcription(
                job.payload, transcriber=transcriber, transcripts=transcripts
            )
    except EmptyTranscript as exc:
        # Terminal: max_attempts=1 spends the whole budget on this one attempt, because
        # the next one would transcribe the same silence and be billed for it.
        return fail(executor, job, f"no words in the recording: {exc}", max_attempts=1)
    except (AsrError, MediaMissing) as exc:
        return fail(executor, job, f"{type(exc).__name__}: {exc}")
    if not complete(executor, job):
        # The lease was reaped and the job handed on. Our result is already stored, so
        # say so and leave the row to its new owner.
        log.warning("job %d finished after its lease had been handed on", job.id)
        return LeaseLost(job_id=job.id)
    return outcome


def work_forever(
    executor: Executor,
    *,
    transcriber: Transcriber,
    transcripts: Transcripts,
    idle_sleep_s: float = IDLE_SLEEP_S,
    sleep: Callable[[float], None] = time.sleep,
    running: Callable[[], bool] = lambda: True,
) -> None:
    """Run jobs until stopped, waiting between empty polls.

    Polling, not LISTEN/NOTIFY: at one job per registered recording, a few seconds of
    delay costs nothing and a second mechanism would have to be operated.
    """
    while running():
        try:
            outcome = work_once(executor, transcriber=transcriber, transcripts=transcripts)
        except Exception:  # one bad job must not end the worker
            log.exception("a transcription job failed outside the queue's own handling")
            outcome = None
        if outcome is None:
            sleep(idle_sleep_s)
        else:
            log.info("transcription job finished: %s", outcome)


__all__ = [
    "IDLE_SLEEP_S",
    "LEASE_SECONDS",
    "MediaMissing",
    "Outcome",
    "Skipped",
    "Stored",
    "run_transcription",
    "work_forever",
    "work_once",
]
