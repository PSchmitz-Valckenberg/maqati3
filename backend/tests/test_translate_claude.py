"""The draft translator, against a fake model client. Never against the network.

The one rule everything here serves: **the row count must be identical in every
language**. A transcript's rows are moments in a recording; a German sentence has to
resolve to the same second as the Arabic it translates, and `validate_transcripts`
refuses anything else. So the translator never merges two lines into one good sentence,
and it says so loudly rather than quietly returning a different number of rows.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from maqati3.domain import Lang
from maqati3.translate import LineCountMismatch, TranslationError, TranslationNotConfigured
from maqati3.translate.claude import DEFAULT_MODEL, ClaudeTranslator

KEY = "sk-ant-test"

ARABIC = ["ما حكم هذا؟", "هذا جائز.", "والله أعلم."]
ENGLISH = ["What is the ruling on this?", "This is permitted.", "And Allah knows best."]


class FakeMessages:
    def __init__(self, replies: list[Any]) -> None:
        self._replies = replies
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        reply = self._replies.pop(0) if len(self._replies) > 1 else self._replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeClient:
    def __init__(self, *replies: Any) -> None:
        self.messages = FakeMessages(list(replies))


class Block:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class Reply:
    """What `messages.create` gives back: content blocks."""

    def __init__(self, lines: list[str]) -> None:
        self.content = [Block(json.dumps({"lines": lines}, ensure_ascii=False))]


def translator(client: Any, **kwargs: Any) -> ClaudeTranslator:
    return ClaudeTranslator(KEY, client=client, **kwargs)


# ------------------------------------------------------------------ no key, no client


def test_a_translator_without_a_key_refuses_to_exist() -> None:
    with pytest.raises(TranslationNotConfigured):
        ClaudeTranslator("")


# ------------------------------------------------------------------ the row count rule


def test_a_reply_with_too_few_lines_is_refused_rather_than_padded() -> None:
    # The tempting repair -- pad with empty rows, or merge -- would put every later
    # line against the wrong second for the rest of the entry's life.
    client = FakeClient(Reply(ENGLISH[:2]))

    with pytest.raises(LineCountMismatch):
        translator(client).translate(ARABIC, source=Lang.AR, target=Lang.EN)


def test_a_reply_with_too_many_lines_is_refused_too() -> None:
    client = FakeClient(Reply([*ENGLISH, "An extra sentence the model felt like adding."]))

    with pytest.raises(LineCountMismatch):
        translator(client).translate(ARABIC, source=Lang.AR, target=Lang.EN)


def test_an_empty_line_stays_an_empty_line() -> None:
    # A translator covered two Arabic rows with one sentence, so one row is empty. The
    # row still exists, and must still exist afterwards.
    client = FakeClient(Reply(["What is the ruling?", ""]))

    result = translator(client).translate(["ما حكم هذا؟", ""], source=Lang.AR, target=Lang.EN)

    assert result == ("What is the ruling?", "")


# ------------------------------------------------------------------ nothing to do


def test_nothing_to_translate_asks_the_model_nothing() -> None:
    client = FakeClient(Reply([]))

    assert translator(client).translate([], source=Lang.AR, target=Lang.EN) == ()
    assert client.messages.calls == []


# ------------------------------------------------------------------ what is asked for


def test_the_request_names_the_draft_model_and_the_two_languages() -> None:
    client = FakeClient(Reply(ENGLISH))

    translator(client).translate(ARABIC, source=Lang.AR, target=Lang.EN)

    (call,) = client.messages.calls
    assert call["model"] == DEFAULT_MODEL
    system = str(call["system"]).lower()
    assert "arabic" in system and "english" in system
    # The schema is what makes the row count answerable at all.
    schema = call["output_config"]["format"]["schema"]
    assert schema["properties"]["lines"]["type"] == "array"


def test_every_line_is_sent_with_its_number_so_none_can_be_dropped_silently() -> None:
    client = FakeClient(Reply(ENGLISH))

    translator(client).translate(ARABIC, source=Lang.AR, target=Lang.EN)

    sent = str(client.messages.calls[0]["messages"][0]["content"])
    for number, line in enumerate(ARABIC, start=1):
        assert f"{number}." in sent
        assert line in sent


def test_a_long_transcript_goes_up_in_chunks_and_comes_back_in_order() -> None:
    # A two-hour lecture is thousands of rows. One request would be slow, expensive to
    # retry, and more likely to lose count.
    lines = [f"سطر {i}" for i in range(10)]
    client = FakeClient(
        Reply([f"line {i}" for i in range(4)]),
        Reply([f"line {i}" for i in range(4, 8)]),
        Reply([f"line {i}" for i in range(8, 10)]),
    )

    result = translator(client, chunk_lines=4).translate(lines, source=Lang.AR, target=Lang.EN)

    assert result == tuple(f"line {i}" for i in range(10))
    assert len(client.messages.calls) == 3


# ------------------------------------------------------------------ when it goes wrong


def test_an_error_from_the_model_is_a_translation_error() -> None:
    client = FakeClient(RuntimeError("upstream exploded"))

    with pytest.raises(TranslationError):
        translator(client).translate(ARABIC, source=Lang.AR, target=Lang.EN)


def test_an_answer_that_is_not_the_agreed_shape_is_refused() -> None:
    class Nonsense:
        content = [Block("sorry, I cannot do that")]

    with pytest.raises(TranslationError):
        translator(FakeClient(Nonsense())).translate(ARABIC, source=Lang.AR, target=Lang.EN)
