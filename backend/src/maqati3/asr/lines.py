"""Word tokens in, transcript rows out.

A provider times every word separately; the archive stores one row per *moment*. That
row is the unit a reviewer corrects, the unit a translation lines up with, and the unit
a deep link points at, so where the cuts fall decides what a citation will quote.

Three things end a row, in the order they are checked: a pause long enough to be a
break in the speech, a sentence mark, and a length limit — Arabic speech runs on for a
long time without a full stop, and a row that holds a whole minute makes "4:12" mean
the minute rather than the sentence.
"""

from __future__ import annotations

from collections.abc import Iterable

from maqati3.asr import AsrLine, AsrToken

#: A gap this long or longer is a break in the speech, not a word boundary.
DEFAULT_MAX_PAUSE_MS = 800

#: Characters. Roughly two lines of Arabic on a phone, and short enough that a row's
#: timestamp still means the sentence next to it.
DEFAULT_MAX_CHARS = 120

#: What ends a sentence in the three languages this archive stores.
SENTENCE_END = frozenset(".!?؟۔")

#: Punctuation that attaches to the word before it. Soniox sends "،" as its own token,
#: and " ،" is wrong in Arabic as well as in German: without this every one of them
#: would be a correction a reviewer has to make by hand.
NO_SPACE_BEFORE = frozenset(".,:;!?،؛؟۔»)]}…”’،")


def _join(line: str, word: str) -> str:
    return line + word if word[0] in NO_SPACE_BEFORE else f"{line} {word}"


def group_tokens(
    tokens: Iterable[AsrToken],
    *,
    max_pause_ms: int = DEFAULT_MAX_PAUSE_MS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> tuple[AsrLine, ...]:
    """Group `tokens` into lines, in order, dropping the ones with no text."""
    lines: list[AsrLine] = []
    text = ""
    start = 0
    end = 0

    for token in tokens:
        word = token.text.strip()
        if not word:
            # Providers emit these around silence. An empty row would still be a row,
            # and the contributor rules forbid deleting rows -- so it is never written.
            continue
        # An end before its start is not trusted: nobody reviews these numbers, and a
        # cue whose end precedes its start is dropped by the player without a word.
        token_end = max(token.end_ms, token.start_ms)

        if text:
            candidate = _join(text, word)
            if token.start_ms - end > max_pause_ms or len(candidate) > max_chars:
                lines.append(AsrLine(t_start_ms=start, t_end_ms=end, text=text))
                text = ""
            else:
                text = candidate
                end = max(end, token_end)
        if not text:
            text = word
            start = token.start_ms
            end = token_end

        if word[-1] in SENTENCE_END:
            lines.append(AsrLine(t_start_ms=start, t_end_ms=end, text=text))
            text = ""

    if text:
        lines.append(AsrLine(t_start_ms=start, t_end_ms=end, text=text))
    return tuple(lines)


__all__ = ["DEFAULT_MAX_CHARS", "DEFAULT_MAX_PAUSE_MS", "group_tokens"]
