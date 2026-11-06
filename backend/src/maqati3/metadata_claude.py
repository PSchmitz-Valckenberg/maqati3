"""Draft an entry's title, question and keywords with Claude Haiku.

A single small request per entry: the whole approved Arabic goes up and three fields come
back in a fixed JSON shape. A person reads and corrects the result, so the model is the
cheap one. There is no field for a ruling and none is asked for.
"""

from __future__ import annotations

import json
from typing import Any

from maqati3.metadata import MetadataDraft, MetadataError, MetadataNotConfigured, tidy_keywords

DEFAULT_MODEL = "claude-haiku-5-5"
MAX_TOKENS = 1500

SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "question": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title", "question", "keywords"],
        "additionalProperties": False,
    },
}


def system_prompt() -> str:
    return """You describe a recorded answer of an Islamic scholar for a library catalogue. \
You are given the Arabic transcript, one line per moment, and you answer in English with a \
JSON object: "title", "question", "keywords".

"title": a short, neutral description of what the recording is about, at most twelve words. \
It names the subject, not the verdict. Never write a ruling of your own, never write "the \
ruling on X is Y", and never state what is permitted or forbidden as a fact: the scholar \
says it, the catalogue does not.

"question": the question the scholar is answering, in one sentence, as it was asked or as \
the answer plainly implies. If the recording contains no question and none is implied, \
return an empty string.

"keywords": three to six lowercase English words or short phrases a visitor might search \
for. Use what is in the text. Do not invent a topic that is not discussed.

Do not add anything the transcript does not say. Do not guess who the speaker is. Do not \
cite a verse or a hadith number that is not written in the transcript. A person will read \
and correct your answer."""


class ClaudeMetadata:
    """`metadata.MetadataDrafter` against the Claude Messages API."""

    def __init__(self, api_key: str, *, model: str = DEFAULT_MODEL, client: Any | None = None):
        if not api_key.strip():
            raise MetadataNotConfigured("ANTHROPIC_API_KEY is empty")
        self._model = model
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
        self._client: Any = client

    def draft(self, lines: tuple[str, ...]) -> MetadataDraft:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=system_prompt(),
                thinking={"type": "disabled"},
                output_config={"effort": "low", "format": SCHEMA},
                messages=[{"role": "user", "content": "\n".join(lines)}],
            )
        except Exception as exc:
            raise MetadataError(f"the model could not be asked: {exc}") from exc
        return _draft_of(response)


def _draft_of(response: Any) -> MetadataDraft:
    try:
        text = next(block.text for block in response.content if block.type == "text")
        payload = json.loads(text)
        title, question, keywords = payload["title"], payload["question"], payload["keywords"]
    except (AttributeError, StopIteration, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise MetadataError(f"the model did not answer in the agreed shape: {exc}") from exc
    if (
        not isinstance(title, str)
        or not isinstance(question, str)
        or not isinstance(keywords, list)
        or not all(isinstance(k, str) for k in keywords)
    ):
        raise MetadataError("the model's fields had the wrong types")
    if not title.strip():
        raise MetadataError("the model gave no title")
    return MetadataDraft(
        title=title.strip(), question=question.strip(), keywords=tidy_keywords(keywords)
    )


__all__ = ["DEFAULT_MODEL", "ClaudeMetadata", "system_prompt"]
