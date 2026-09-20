"""A deterministic, GPU-free engine for tests and local development.

Given the same State and Questions it always returns the same well-formed
answers, so contract tests can drive the real SDK against it in CI without a
model or a GPU.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Sequence

from laya_server.inference.base import PredictResult
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


def _rng(*parts: str) -> random.Random:
    """A Random seeded stably from the given parts (stable across processes)."""
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def _distribution(rng: random.Random, keys: Sequence[str]) -> dict[str, float]:
    """A deterministic probability distribution over ``keys`` summing to ~1."""
    weights = [rng.random() + 0.1 for _ in keys]
    total = sum(weights)
    return {
        key: round(weight / total, 4) for key, weight in zip(keys, weights, strict=True)
    }


def _argmax(probabilities: dict[str, float]) -> str:
    """The key with the highest probability."""
    return max(probabilities, key=probabilities.__getitem__)


class FakeEngine:
    """Deterministic engine implementing the ``DecisionEngine`` protocol."""

    def is_ready(self) -> bool:
        return True

    def predict(
        self, state: JSONContent, questions: dict[str, Question]
    ) -> PredictResult:
        answers: dict[str, Answer] = {}
        for name, question in questions.items():
            rng = _rng(name, question.type)
            if isinstance(question, NoulQuestion):
                answers[name] = self._noul(rng)
            elif isinstance(question, ChoiceQuestion):
                answers[name] = self._choice(rng, question)
            elif isinstance(question, ScoreQuestion):
                answers[name] = self._score(rng, question)
        return PredictResult(
            answers=answers, input_tokens=self._estimate_tokens(state, questions)
        )

    def _noul(self, rng: random.Random) -> NoulAnswer:
        return NoulAnswer(noul=round(rng.random(), 4))

    def _choice(self, rng: random.Random, question: ChoiceQuestion) -> ChoiceAnswer:
        probabilities = _distribution(rng, list(question.criteria))
        choice = _argmax(probabilities)
        return ChoiceAnswer(
            choice=choice,
            confidence=probabilities[choice],
            probabilities=probabilities,
        )

    def _score(self, rng: random.Random, question: ScoreQuestion) -> ScoreAnswer:
        levels = [str(index) for index in range(len(question.criteria))]
        probabilities = _distribution(rng, levels)
        expected = sum(int(level) * prob for level, prob in probabilities.items())
        top = _argmax(probabilities)
        legend: dict[str, JSONContent] = {
            str(index): description
            for index, description in enumerate(question.criteria)
        }
        return ScoreAnswer(
            score=round(expected, 4),
            confidence=probabilities[top],
            legend=legend,
            probabilities=probabilities,
        )

    def _estimate_tokens(
        self, state: JSONContent, questions: dict[str, Question]
    ) -> int:
        blob = json.dumps(
            {
                "state": state,
                "questions": {name: q.model_dump() for name, q in questions.items()},
            },
            default=str,
            sort_keys=True,
        )
        return max(1, len(blob) // 4)
