"""Normalising a recording before it leaves for the transcription provider.

What contributors send is phone video: an H.264 picture nobody will ever watch wrapped
around a few minutes of speech. The transcript is the same either way, so only the
audio goes up — 24 kbit/s mono Opus, the format `docs/ARCHITECTURE.md` settled on for
the archive itself. A 200 MB forward becomes about 1 MB per minute, which is the
difference between a worker that finishes and one that times out on a home connection.

Two things this must never do: touch the original (it is the only copy there is until
an entry is published), and move the timeline. The timestamps the provider returns are
offsets into this file, and the deep link to the second is the product.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from maqati3.dedup.fingerprint import UnreadableMedia

#: `docs/ARCHITECTURE.md`: Opus 24 kbit/s mono. Speech stays intelligible well below
#: this, and the provider is paid by audio hour, not by megabyte.
DEFAULT_BITRATE = "24k"

#: Opus is defined at 48 kHz; anything else makes libopus resample twice.
SAMPLE_RATE = 48_000

#: A two-hour lecture re-encodes in well under this. A hung ffmpeg must not hold a
#: worker's lease open for ever.
DEFAULT_TIMEOUT_S = 1800

PREPARED_NAME = "audio.opus"


def prepare_for_asr(
    source: Path,
    workdir: Path,
    *,
    ffmpeg: str = "ffmpeg",
    bitrate: str = DEFAULT_BITRATE,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Path:
    """Write `source`'s audio to `workdir` as mono Opus and return the new file.

    Raises `UnreadableMedia` when there is no audio to send — a photo, a silent screen
    recording, a document renamed to .mp4. Finding that out here costs nothing; finding
    it out from the provider costs a transcription of silence.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    destination = workdir / PREPARED_NAME
    command = [
        ffmpeg,
        "-nostdin",          # a worker has no terminal; ffmpeg must never wait for one
        "-v", "error",
        "-y",
        "-i", str(source),
        "-vn",               # leave the picture behind
        "-ac", "1",
        "-ar", str(SAMPLE_RATE),
        "-c:a", "libopus",
        "-b:a", bitrate,
        str(destination),
    ]
    # A missing binary raises FileNotFoundError and is left to propagate: a broken
    # server must not look like an unusable recording.
    try:
        proc = subprocess.run(command, capture_output=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired as exc:
        raise UnreadableMedia(f"re-encoding {source.name} took longer than {timeout_s}s") from exc
    if proc.returncode != 0:
        reason = proc.stderr.decode(errors="replace").strip() or f"exit {proc.returncode}"
        raise UnreadableMedia(f"{source.name} has no audio that could be read: {reason}")
    if not destination.exists() or destination.stat().st_size == 0:
        raise UnreadableMedia(f"{source.name} produced no audio")
    return destination


__all__ = ["DEFAULT_BITRATE", "PREPARED_NAME", "prepare_for_asr"]
