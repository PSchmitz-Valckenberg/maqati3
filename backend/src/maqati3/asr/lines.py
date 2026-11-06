"""Tokens in, transcript rows out.

A provider times every token separately; the archive stores one row per *moment*. That
row is the unit a reviewer corrects, the unit a translation lines up with, and the unit
a deep link points at, so where the cuts fall decides what a citation will quote.

A token is a piece of a word, not a word: Soniox sends "ربنا" as "ر", "ب", "نا". The
first piece of a word carries a leading space and the others do not, so that space is
the only mark of where a word begins. Everything here follows from it: pieces without
one are glued to the word before, and a row is only ever cut where a word begins.

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


def group_tokens(
    tokens: Iterable[AsrToken],
    *,
    max_pause_ms: int = DEFAULT_MAX_PAUSE_MS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> tuple[AsrLine, ...]:
    """Group `tokens` into lines, in order, dropping the ones with no text.

    `token.text` is what the provider sent, spacing included: a leading space starts a
    word, anything else continues the one before. That covers punctuation too, which
    arrives as a token of its own ("،", ".") and belongs to the word it follows.
    """
    lines: list[AsrLine] = []
    text = ""
    start = 0
    end = 0
    after_space = False

    for token in tokens:
        piece = token.text.strip()
        if not piece:
            # Providers emit these around silence. An empty row would still be a row,
            # and the contributor rules forbid deleting rows -- so it is never written.
            # A bare space still says the next piece begins a word.
            after_space = after_space or bool(token.text)
            continue
        word_start = after_space or token.text[0].isspace()
        after_space = False
        # An end before its start is not trusted: nobody reviews these numbers, and a
        # cue whose end precedes its start is dropped by the player without a word.
        token_end = max(token.end_ms, token.start_ms)

        if text and not word_start:
            # The rest of a word, or a mark closing it: never a place to cut, however
            # long the silence before it. A "." that came late stays on its sentence.
            text += piece
            end = max(end, token_end)
        elif text:
            candidate = f"{text} {piece}"
            if token.start_ms - end > max_pause_ms or len(candidate) > max_chars:
                lines.append(AsrLine(t_start_ms=start, t_end_ms=end, text=text))
                text, start, end = piece, token.start_ms, token_end
            else:
                text = candidate
                end = max(end, token_end)
        else:
            text, start, end = piece, token.start_ms, token_end

        if piece[-1] in SENTENCE_END:
            lines.append(AsrLine(t_start_ms=start, t_end_ms=end, text=text))
            text = ""

    if text:
        lines.append(AsrLine(t_start_ms=start, t_end_ms=end, text=text))
    return tuple(lines)


__all__ = ["DEFAULT_MAX_CHARS", "DEFAULT_MAX_PAUSE_MS", "group_tokens"]
