"""The backend image must contain every external program the code runs.

Found on the first real run on the server (2026-11-23): the worker needs `ffmpeg` to cut
the sound out of a phone video, the image only had `fpcalc`, and every transcription
failed. It never showed locally because a developer's machine has both. A test that reads
the Dockerfile is a blunt guard, and exactly as blunt as the mistake it prevents.
"""

from __future__ import annotations

from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[2] / "backend" / "Dockerfile"

#: Program name in the code -> the Debian package that provides it.
REQUIRED_PACKAGES = {
    "fpcalc": "libchromaprint-tools",  # dedup/chromaprint.py: fingerprints at upload
    "ffmpeg": "ffmpeg",  # media.py: the audio that is sent to the transcription provider
}


def test_the_image_installs_every_program_the_code_runs() -> None:
    text = DOCKERFILE.read_text()

    missing = [
        f"{program} (package {package})"
        for program, package in REQUIRED_PACKAGES.items()
        if package not in text
    ]

    assert missing == [], f"backend/Dockerfile does not install: {', '.join(missing)}"
