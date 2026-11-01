"""The boundary to the model that drafts translations.

One rule stands above the rest and shapes every type here: **the row count is identical
in every language**. A transcript's rows are moments in a recording, and the German
sentence on row 42 has to resolve to the same second as the Arabic on row 42 — that is
the whole product. So a translator returns exactly as many lines as it was given, in the
same order, or it raises. Merging two short lines into one good sentence is the natural
thing for a translator to do and the one thing this one may never do.

What comes out is a *draft*: stored with `machine_translation` provenance, never public
until a person has approved that language (`register.gates`). The Arabic stays next to
it, always.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from maqati3.domain import Lang


class TranslationError(Exception):
    """No usable draft came back. The job retries; nothing is stored."""


class TranslationNotConfigured(TranslationError):
    """No API key. The button that would spend money is not offered at all."""


class LineCountMismatch(TranslationError):
    """The model returned a different number of lines than it was given.

    Never repaired by padding or merging: either would put every line after the
    mistake against the wrong second, for as long as the entry exists.
    """


class Translator(Protocol):
    """Lines in, the same number of lines out."""

    def translate(
        self, lines: Sequence[str], *, source: Lang, target: Lang
    ) -> tuple[str, ...]:
        """Raises `TranslationError` for anything that leaves no usable draft."""
        ...


__all__ = [
    "LineCountMismatch",
    "TranslationError",
    "TranslationNotConfigured",
    "Translator",
]
