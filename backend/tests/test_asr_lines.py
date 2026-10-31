"""Turning an ASR provider's word tokens into transcript lines.

Soniox answers with one token per word, each with its own start and end. The archive
stores one row per *moment* instead, because that is the unit a reviewer corrects, a
translation lines up with, and a deep link points at. Where those rows are cut is
therefore not cosmetic: it decides what a citation will quote.

Nothing here talks to a provider. `group_tokens` is a pure function over tokens.
"""

from __future__ import annotations

from maqati3.asr import AsrToken
from maqati3.asr.lines import DEFAULT_MAX_CHARS, DEFAULT_MAX_PAUSE_MS, group_tokens


def tokens(*items: tuple[str, int, int]) -> list[AsrToken]:
    return [AsrToken(text=text, start_ms=start, end_ms=end) for text, start, end in items]


def test_no_tokens_make_no_lines() -> None:
    assert group_tokens([]) == ()


def test_a_token_with_no_text_never_becomes_a_line() -> None:
    # A provider emits these around silence. An empty row would still be a row the
    # reviewer may not delete -- the validator forbids removing rows - so it must never
    # be written in the first place.
    assert group_tokens(tokens((" ", 0, 100), ("", 100, 200))) == ()


def test_a_line_starts_at_its_first_token_and_ends_at_its_last() -> None:
    line, = group_tokens(tokens(("ما", 0, 300), ("حكم", 300, 700), ("هذا؟", 700, 1200)))

    assert (line.t_start_ms, line.t_end_ms) == (0, 1200)
    assert line.text == "ما حكم هذا؟"


def test_a_sentence_mark_ends_the_line() -> None:
    lines = group_tokens(tokens(("هذا", 0, 300), ("جائز.", 300, 800), ("والله", 900, 1300)))

    assert [line.text for line in lines] == ["هذا جائز.", "والله"]
    assert [line.t_start_ms for line in lines] == [0, 900]


def test_a_pause_ends_the_line_even_mid_sentence() -> None:
    # The scholar stops to think. Keeping both halves on one row would make the row's
    # timestamp point seconds before the words a reader sees next to it.
    gap = DEFAULT_MAX_PAUSE_MS + 1
    lines = group_tokens(tokens(("وأما", 0, 400), ("الثاني", 400 + gap, 900 + gap)))

    assert [line.text for line in lines] == ["وأما", "الثاني"]


def test_a_pause_shorter_than_the_limit_keeps_the_line_together() -> None:
    gap = DEFAULT_MAX_PAUSE_MS - 1
    lines = group_tokens(tokens(("وأما", 0, 400), ("الثاني", 400 + gap, 900 + gap)))

    assert [line.text for line in lines] == ["وأما الثاني"]


def test_a_line_is_cut_before_it_grows_past_the_limit() -> None:
    # Arabic speech runs on without a full stop for a long time. Without this a single
    # row could hold a whole minute, and a citation would quote the minute.
    word = "كلمة"
    many = tokens(*((word, i * 400, i * 400 + 300) for i in range(200)))

    lines = group_tokens(many)

    assert len(lines) > 1
    assert all(len(line.text) <= DEFAULT_MAX_CHARS for line in lines)
    assert " ".join(line.text for line in lines) == " ".join([word] * 200)


def test_lines_follow_each_other_in_time_and_never_overlap() -> None:
    lines = group_tokens(
        tokens(("أ.", 0, 200), ("ب.", 500, 900), ("ج.", 1000, 1500), ("د", 3000, 3400))
    )

    starts = [line.t_start_ms for line in lines]
    assert starts == sorted(starts)
    assert all(a.t_end_ms <= b.t_start_ms for a, b in zip(lines, lines[1:], strict=False))


def test_a_token_that_is_only_punctuation_joins_the_word_before_it() -> None:
    # Soniox emits "،" as its own token. " ،" in the middle of a line is wrong in Arabic
    # and wrong in German, and a reviewer would have to fix every one of them by hand.
    line, = group_tokens(tokens(("نعم", 0, 300), ("،", 300, 320), ("لكن", 400, 800)))

    assert line.text == "نعم، لكن"


def test_tokens_that_carry_their_own_spacing_do_not_get_doubled_spaces() -> None:
    # Providers differ: some send "word", some send " word". Both have to come out as
    # one space between words, because the text is shown to a reader as it is stored.
    line, = group_tokens(tokens(("نعم", 0, 300), (" لكن", 300, 800)))

    assert line.text == "نعم لكن"


def test_an_end_before_its_start_is_not_trusted() -> None:
    # Timestamps from a provider are not reviewed by anyone. A row whose end precedes
    # its start would make the player drop the cue silently.
    line, = group_tokens(tokens(("كلمة", 1000, 400)))

    assert line.t_start_ms <= line.t_end_ms
