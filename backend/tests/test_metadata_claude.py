"""The model that drafts an entry's title, question and keywords, against a fake client."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from maqati3.metadata import MetadataError, MetadataNotConfigured
from maqati3.metadata_claude import ClaudeMetadata, system_prompt


class Client:
    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.calls: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.reply, Exception):
            raise self.reply
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.reply)])


GOOD = json.dumps(
    {"title": "On kindness", "question": "How to treat a mother?", "keywords": ["family", "mother"]}
)


def drafter(client: Client) -> ClaudeMetadata:
    return ClaudeMetadata("key", client=client)


def test_without_a_key_it_refuses_to_exist() -> None:
    with pytest.raises(MetadataNotConfigured):
        ClaudeMetadata("")


def test_the_arabic_goes_up_and_the_draft_comes_back() -> None:
    client = Client(GOOD)

    draft = drafter(client).draft(("ما حكم هذا؟", "هذا جائز."))

    assert (draft.title, draft.question, draft.keywords) == (
        "On kindness",
        "How to treat a mother?",
        ("family", "mother"),
    )
    assert "ما حكم هذا؟" in client.calls[0]["messages"][0]["content"]


@pytest.mark.parametrize(
    "reply",
    ["not json", "{}", json.dumps({"title": 3, "question": "", "keywords": []}),
     json.dumps({"title": "T", "question": "", "keywords": "family"})],
)
def test_an_answer_in_the_wrong_shape_is_a_failure_not_a_partial_draft(reply: str) -> None:
    with pytest.raises(MetadataError):
        drafter(Client(reply)).draft(("x",))


def test_a_model_that_cannot_be_asked_is_a_metadata_error() -> None:
    with pytest.raises(MetadataError):
        drafter(Client(RuntimeError("down"))).draft(("x",))


def test_an_empty_title_is_not_a_draft() -> None:
    reply = json.dumps({"title": " ", "question": "", "keywords": []})
    with pytest.raises(MetadataError):
        drafter(Client(reply)).draft(("x",))


def test_the_prompt_forbids_a_ruling_of_its_own_and_any_invention() -> None:
    prompt = system_prompt()
    assert "ruling" in prompt
    assert "Do not" in prompt
