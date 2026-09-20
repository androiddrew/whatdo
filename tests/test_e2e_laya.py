"""Full end-to-end suite: real SDK -> app -> real LayaEngine on a checkpoint.

Marked ``slow``: requires the ``laya`` extra and downloads a real checkpoint
(runs best on a GPU). It is excluded from ``make test`` and skipped in CI (laya
is not installed there); run it with ``make test-slow`` on a suitable machine.
"""

from __future__ import annotations

import pytest
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

from laya_server.app import create_app
from tests.conftest import serve

pytestmark = pytest.mark.slow


def test_end_to_end_with_real_laya(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("laya")
    from laya_server.inference.laya_engine import LayaEngine

    app = create_app(engine=LayaEngine())
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

    with serve(app, startup_timeout=600) as base_url:
        monkeypatch.setenv("TYPESAFE_BASE_URL", base_url)
        with TypeSafeClient() as client:
            response = client.system_one(
                state="I was charged twice. Please help.",
                questions={
                    "billing": Noul(instructions="Is this about billing?"),
                    "tone": Choice(
                        instructions="What is the tone?",
                        criteria={"angry": None, "calm": None},
                    ),
                    "urgency": Score(
                        instructions="How urgent is this?",
                        criteria=["low", "medium", "high"],
                    ),
                },
            )

    assert 0.0 <= response.nouls["billing"].noul <= 1.0
    assert response.choices["tone"].choice in {"angry", "calm"}
    assert set(response.scores["urgency"].legend) == {0, 1, 2}
    assert response.usage.input_tokens is not None
    assert response.usage.input_tokens > 0
