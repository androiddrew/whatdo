"""LayaEngine wiring tests using a stub agent (no laya/GPU needed)."""

from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Any

import pytest

from whatdo.inference import laya_engine
from whatdo.inference.laya_engine import LayaEngine
from whatdo.schemas.jev import ChoiceAnswer, NoulAnswer, NoulQuestion


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


def test_repr_describes_the_checkpoint_and_device() -> None:
    engine = LayaEngine(checkpoint="org/ckpt", device="cuda:1", subfolder="en")
    assert repr(engine) == (
        "LayaEngine(checkpoint='org/ckpt', device='cuda:1', subfolder='en')"
    )


def test_predict_logs_questions_and_answers_at_debug(
    whatdo_logs: list[logging.LogRecord],
) -> None:
    engine = LayaEngine(agent=_StubAgent())
    engine.predict({"secret": "user data"}, {"billing": NoulQuestion()})
    messages = [
        r.getMessage() for r in whatdo_logs if r.name == "whatdo.inference.laya_engine"
    ]
    assert any("'billing'" in m and "'noul'" in m for m in messages)
    assert any("input_tokens=42" in m for m in messages)
    # The state may carry user data and is never logged.
    assert not any("user data" in m for m in messages)


class _RecordingLaya:
    """Stands in for the ``laya`` module, recording how ``load`` calls overlap."""

    def __init__(self, fail_first: bool = False) -> None:
        self.events: list[tuple[str, int]] = []
        self._fail_first = fail_first
        self._lock = threading.Lock()
        self._calls = 0

    def load(self, checkpoint: str, **_: Any) -> _StubAgent:
        with self._lock:
            call = self._calls
            self._calls += 1
            self.events.append(("start", call))
        # Long enough that unserialized loads would interleave.
        time.sleep(0.05)
        with self._lock:
            self.events.append(("end", call))
        if self._fail_first and call == 0:
            raise RuntimeError("download interrupted")
        return _StubAgent()


def _load_concurrently(engines: list[LayaEngine]) -> list[BaseException]:
    errors: list[BaseException] = []

    def run(engine: LayaEngine) -> None:
        try:
            engine.load()
        except BaseException as error:  # noqa: BLE001 - collected for asserts
            errors.append(error)

    threads = [threading.Thread(target=run, args=(e,)) for e in engines]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    return errors


@pytest.fixture
def recording_laya(monkeypatch: pytest.MonkeyPatch) -> _RecordingLaya:
    """A stub ``laya`` on a process that has not loaded a checkpoint yet."""
    stub = _RecordingLaya()
    monkeypatch.setitem(sys.modules, "laya", stub)
    monkeypatch.setattr(laya_engine, "_first_load_done", False)
    return stub


def test_first_load_runs_alone_then_copies_load_in_parallel(
    recording_laya: _RecordingLaya,
) -> None:
    engines = [LayaEngine() for _ in range(3)]
    assert _load_concurrently(engines) == []
    assert all(engine.is_ready() for engine in engines)

    events = recording_laya.events
    # The first load finishes before any other starts (laya/transformers lazy
    # imports aren't thread-safe on a cold process)...
    assert events[:2] == [("start", 0), ("end", 0)]
    # ...and the remaining copies then overlap rather than queue up.
    assert events[2:4] == [("start", 1), ("start", 2)]


def test_failed_first_load_leaves_the_next_load_serialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _RecordingLaya(fail_first=True)
    monkeypatch.setitem(sys.modules, "laya", stub)
    monkeypatch.setattr(laya_engine, "_first_load_done", False)

    errors = _load_concurrently([LayaEngine() for _ in range(3)])

    assert [str(error) for error in errors] == ["download interrupted"]
    # Call 0 failed, so call 1 still ran alone before call 2 started.
    assert stub.events[:4] == [("start", 0), ("end", 0), ("start", 1), ("end", 1)]
