"""LayaEngine wiring tests using a stub agent (no laya/GPU needed)."""

from __future__ import annotations

from typing import Any

import pytest

from laya_server.inference.laya_engine import LayaEngine
from laya_server.schemas.jev import ChoiceAnswer, NoulAnswer, NoulQuestion


class _StubAgent:
    """Stands in for a loaded laya Agent, returning laya-shaped answers."""

    def __init__(self) -> None:
        self.seen: dict[str, Any] | None = None

    def predict(self, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        self.seen = questions
        return {
            "model": "laya-rl-agent",
            "answers": {
                "billing": {
                    "type": "noul",
                    "noul": 0.9,
                    "confidence": 0.9,
                    "action": {"act_probability": 0.5},
                },
                "tone": {
                    "type": "choice",
                    "choice": "angry",
                    "probabilities": {"angry": 0.8, "calm": 0.2},
                    "confidence": 0.8,
                    "action": {},
                },
            },
            "usage": {"input_tokens": 42, "output_tokens": 0},
        }


def test_engine_translates_agent_output() -> None:
    engine = LayaEngine(agent=_StubAgent())
    engine.load()  # no-op with an injected agent
    assert engine.is_ready()

    result = engine.predict("hi", {"billing": NoulQuestion(instructions="spam?")})

    assert isinstance(result.answers["billing"], NoulAnswer)
    assert result.answers["billing"].noul == 0.9
    assert isinstance(result.answers["tone"], ChoiceAnswer)
    assert result.input_tokens == 42


def test_engine_forwards_translated_questions() -> None:
    agent = _StubAgent()
    engine = LayaEngine(agent=agent)
    engine.predict("hi", {"billing": NoulQuestion()})
    assert agent.seen == {"billing": {"type": "noul", "instructions": ""}}


def test_predict_before_load_raises() -> None:
    engine = LayaEngine()
    with pytest.raises(RuntimeError):
        engine.predict("hi", {})
