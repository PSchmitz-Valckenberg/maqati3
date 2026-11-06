"""Turning an ASR provider's tokens into transcript lines.

Soniox answers with *pieces of words*, not words: "ربنا" arrives as "ر", "ب", "نا". The
first piece of every word carries a leading space and the rest do not, so that space is
the only thing that says where a word begins (captured from a real run, 2026-11-06). The
archive stores one row per *moment*, because that is the unit a reviewer corrects, a
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


def test_pieces_of_one_word_are_joined_without_a_space() -> None:
    # The bug this file now guards: every piece got a space of its own, so "ربنا" was
    # stored as "ر ب نا" and a reviewer would have had to repair every word by hand.
    (line,) = group_tokens(
        tokens(
            ("ر", 150, 210),
            ("ب", 270, 330),
            ("نا", 450, 510),
            (" سب", 570, 630),
            ("حانه", 690, 930),
        )
    )

    assert line.text == "ربنا سبحانه"


def test_a_word_start_is_a_leading_space_and_nothing_else() -> None:
    (line,) = group_tokens(tokens((" و", 0, 60), ("قال", 60, 300), (" ربك", 300, 700)))

    assert line.text == "وقال ربك"


def test_the_first_piece_of_the_recording_needs_no_leading_space() -> None:
    (line,) = group_tokens(tokens(("ما", 0, 300), (" حكم", 300, 700), (" هذا؟", 700, 1200)))

    assert (line.t_start_ms, line.t_end_ms) == (0, 1200)
    assert line.text == "ما حكم هذا؟"


def test_a_sentence_mark_ends_the_line() -> None:
    lines = group_tokens(
        tokens(("هذا", 0, 300), (" جائز", 300, 700), (".", 700, 760), (" والله", 900, 1300))
    )

    assert [line.text for line in lines] == ["هذا جائز.", "والله"]
    assert [line.t_start_ms for line in lines] == [0, 900]


def test_a_mark_after_a_pause_stays_with_the_sentence_it_closes() -> None:
    # Real: the "." came 300 ms after the last word, past the pause limit, and became a
    # row of its own at the wrong second. A mark closes the sentence; it never starts one.
    gap = DEFAULT_MAX_PAUSE_MS + 1
    lines = group_tokens(
        tokens(("جائز", 0, 400), (".", 400 + gap, 460 + gap), (" والله", 2000, 2400))
    )

    assert [line.text for line in lines] == ["جائز.", "والله"]


def test_a_pause_ends_the_line_even_mid_sentence() -> None:
    # The scholar stops to think. Keeping both halves on one row would make the row's
    # timestamp point seconds before the words a reader sees next to it.
    gap = DEFAULT_MAX_PAUSE_MS + 1
    lines = group_tokens(tokens(("وأما", 0, 400), (" الثاني", 400 + gap, 900 + gap)))

    assert [line.text for line in lines] == ["وأما", "الثاني"]


def test_a_pause_shorter_than_the_limit_keeps_the_line_together() -> None:
    gap = DEFAULT_MAX_PAUSE_MS - 1
    lines = group_tokens(tokens(("وأما", 0, 400), (" الثاني", 400 + gap, 900 + gap)))

    assert [line.text for line in lines] == ["وأما الثاني"]


def test_a_long_gap_inside_a_word_never_cuts_the_word() -> None:
    # A row is cut where a word begins. A stretched syllable can leave a gap between two
    # pieces of one word, and a cut there would store half a word on each row.
    gap = DEFAULT_MAX_PAUSE_MS + 500
    (line,) = group_tokens(tokens((" سب", 0, 300), ("حانه", 300 + gap, 700 + gap)))

    assert line.text == "سبحانه"


def test_a_line_is_cut_before_it_grows_past_the_limit() -> None:
    # Arabic speech runs on without a full stop for a long time. Without this a single
    # row could hold a whole minute, and a citation would quote the minute.
    word = "كلمة"
    many = tokens(*((f" {word}", i * 400, i * 400 + 300) for i in range(200)))

    lines = group_tokens(many)

    assert len(lines) > 1
    assert all(len(line.text) <= DEFAULT_MAX_CHARS for line in lines)
    assert " ".join(line.text for line in lines) == " ".join([word] * 200)


def test_a_line_is_never_cut_inside_a_word_when_it_runs_long() -> None:
    pieces = [
        piece
        for i in range(100)
        for piece in ((" كل", i * 400, i * 400 + 150), ("مة", i * 400 + 150, i * 400 + 300))
    ]

    lines = group_tokens(tokens(*pieces))

    assert len(lines) > 1
    assert all(word == "كلمة" for line in lines for word in line.text.split())


def test_lines_follow_each_other_in_time_and_never_overlap() -> None:
    lines = group_tokens(
        tokens(
            ("أ", 0, 150),
            (".", 150, 200),
            (" ب", 500, 800),
            (".", 800, 900),
            (" ج", 1000, 1400),
            (".", 1400, 1500),
            (" د", 3000, 3400),
        )
    )

    starts = [line.t_start_ms for line in lines]
    assert starts == sorted(starts)
    assert all(a.t_end_ms <= b.t_start_ms for a, b in zip(lines, lines[1:], strict=False))


def test_a_token_that_is_only_punctuation_joins_the_word_before_it() -> None:
    # Soniox emits "،" as its own token. " ،" in the middle of a line is wrong in Arabic
    # and wrong in German, and a reviewer would have to fix every one of them by hand.
    (line,) = group_tokens(tokens(("نعم", 0, 300), ("،", 300, 320), (" لكن", 400, 800)))

    assert line.text == "نعم، لكن"


def test_a_token_that_is_only_a_space_marks_the_next_one_as_a_word_start() -> None:
    (line,) = group_tokens(tokens(("نعم", 0, 300), (" ", 300, 320), ("لكن", 320, 800)))

    assert line.text == "نعم لكن"


def test_spacing_is_never_doubled() -> None:
    (line,) = group_tokens(tokens(("نعم", 0, 300), (" ", 300, 320), (" لكن", 320, 800)))

    assert line.text == "نعم لكن"


def test_an_end_before_its_start_is_not_trusted() -> None:
    # Timestamps from a provider are not reviewed by anyone. A row whose end precedes
    # its start would make the player drop the cue silently.
    (line,) = group_tokens(tokens(("كلمة", 1000, 400)))

    assert line.t_start_ms <= line.t_end_ms


def test_the_opening_of_a_real_recording_reads_as_words() -> None:
    # The first tokens of the 80-second test clip as Soniox sent them (rounded, the
    # confidence fields left out), an opening of Sūrat an-Nisāʾ 4:29.
    real = tokens(
        ("ر", 150, 210),
        ("ب", 270, 330),
        ("نا", 450, 510),
        (" سب", 570, 630),
        ("ح", 690, 750),
        ("انه", 870, 930),
        (" وت", 1110, 1170),
        ("ع", 1230, 1290),
        ("ال", 1290, 1350),
        ("ى", 1410, 1470),
        (" ي", 1590, 1650),
        ("ق", 1710, 1770),
        ("ول", 1770, 1830),
        (":", 2130, 2190),
    )

    (line,) = group_tokens(real)

    assert line.text == "ربنا سبحانه وتعالى يقول:"
