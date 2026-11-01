"""Normalising a recording before it is sent to the transcription provider.

Against the real ffmpeg and real (generated) audio; skipped where ffmpeg is missing.
Media never goes into git (WORKFLOW.md), so the test makes its own.

Why this exists at all: contributors send phone videos. A 200 MB MP4 and the 1 MB of
mono Opus inside it produce the same transcript, and only one of them has to be pushed
up a home connection first.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from maqati3.dedup.fingerprint import UnreadableMedia
from maqati3.media import prepare_for_asr

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="integration test: needs ffmpeg on PATH"
)


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


@pytest.fixture(scope="module")
def phone_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """What actually arrives: a short video with a stereo soundtrack."""
    folder = tmp_path_factory.mktemp("media")
    path = folder / "forward.mp4"
    ffmpeg(
        "-f", "lavfi", "-i", "testsrc=size=640x480:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
        "-t", "4", "-ac", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(path),
    )
    return path


def test_a_file_with_no_sound_is_refused_before_anything_is_uploaded(tmp_path: Path) -> None:
    # A photo or a silent screen recording. Sending it would be paid for and come back
    # empty; the worker must learn that here, not from the provider's bill.
    silent = tmp_path / "screen.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc=size=320x240:rate=15", "-t", "2",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", str(silent))

    with pytest.raises(UnreadableMedia):
        prepare_for_asr(silent, tmp_path / "work")


def test_a_file_that_is_not_media_at_all_is_refused(tmp_path: Path) -> None:
    garbage = tmp_path / "document.mp4"
    garbage.write_bytes(b"a document renamed to .mp4")

    with pytest.raises(UnreadableMedia):
        prepare_for_asr(garbage, tmp_path / "work")


def test_the_original_is_never_touched(tmp_path: Path, phone_video: Path) -> None:
    # The staged upload is the only copy there is until an entry is published.
    before = phone_video.read_bytes()

    prepare_for_asr(phone_video, tmp_path / "work")

    assert phone_video.read_bytes() == before


def test_the_video_is_left_behind_and_what_goes_up_is_small_mono_audio(
    tmp_path: Path, phone_video: Path
) -> None:
    prepared = prepare_for_asr(phone_video, tmp_path / "work")

    assert prepared.exists()
    assert prepared.stat().st_size < phone_video.stat().st_size
    streams = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,channels",
         "-of", "csv=p=0", str(prepared)],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert streams == ["opus,1"]


def test_the_audio_keeps_its_length_to_the_second(tmp_path: Path, phone_video: Path) -> None:
    # The timestamps the provider returns are offsets into this file. If normalising
    # moved them, every deep link in the archive would be wrong by that much.
    prepared = prepare_for_asr(phone_video, tmp_path / "work")

    def seconds(path: Path) -> float:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return float(out)

    assert abs(seconds(prepared) - seconds(phone_video)) < 1.0
