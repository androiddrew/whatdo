"""Translation between the Jev wire schema and Laya's own question/answer dicts.

Kept as pure functions so they can be unit-tested without laya or a GPU. Laya's
answer dicts are almost Jev-shaped but carry an extra ``action`` key, and its
noul answer includes a ``confidence`` that Jev's noul does not; both are dropped
here by only reading the fields Jev defines.
"""

from __future__ import annotations

import json
from typing import Any

from laya_server.schemas.jev import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    JSONContent,
    NoulAnswer,
    NoulQuestion,
    Question,
    ScoreAnswer,
    ScoreQuestion,
)


def _as_text(value: JSONContent) -> str:
    """Laya expects text for criteria descriptions; encode objects/lists as JSON."""
    return value if isinstance(value, str) else json.dumps(value)


def to_laya_question(question: Question) -> dict[str, Any]:
    """Convert a Jev question model into the dict Laya's ``predict`` expects.

    Laya requires an ``instructions`` key on every question, so a missing one
    becomes an empty string.
    """
    instructions: JSONContent = (
        "" if question.instructions is None else question.instructions
    )
    if isinstance(question, NoulQuestion):
        laya_question: dict[str, Any] = {"type": "noul", "instructions": instructions}
        # Laya's noul consumes true/false descriptions (see laya render_options),
        # so forward them when present.
        if question.criteria is not None:
            laya_question["criteria"] = {
                "true": question.criteria.true,
                "false": question.criteria.false,
            }
        return laya_question
    if isinstance(question, ChoiceQuestion):
        criteria = {
            label: (None if desc is None else _as_text(desc))
            for label, desc in question.criteria.items()
        }
        return {"type": "choice", "instructions": instructions, "criteria": criteria}
    if isinstance(question, ScoreQuestion):
        return {
            "type": "score",
            "instructions": instructions,
            "criteria": [_as_text(level) for level in question.criteria],
        }
    raise TypeError(
        f"unsupported question type: {type(question)!r}"
    )  # pragma: no cover


def _probs(raw: dict[str, Any]) -> dict[str, float]:
    return {key: float(value) for key, value in raw.items()}


def to_jev_answer(answer: dict[str, Any]) -> Answer:
    """Convert one of Laya's answer dicts into a Jev answer model."""
    answer_type = answer["type"]
    if answer_type == "noul":
        return NoulAnswer(noul=float(answer["noul"]))
    if answer_type == "choice":
        return ChoiceAnswer(
            choice=answer["choice"],
            confidence=float(answer["confidence"]),
            probabilities=_probs(answer["probabilities"]),
        )
    if answer_type == "score":
        return ScoreAnswer(
            score=float(answer["score"]),
            confidence=float(answer["confidence"]),
            legend=answer["legend"],
            probabilities=_probs(answer["probabilities"]),
        )
    raise ValueError(f"unknown answer type: {answer_type!r}")
