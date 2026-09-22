"""Full end-to-end suite: real SDK -> app -> real LayaEngine on a checkpoint.

Marked ``slow``: requires the ``laya`` extra and downloads a real checkpoint
(runs best on a GPU). It is excluded from ``make test`` and skipped in CI (laya
is not installed there); run it with ``make test-slow`` on a suitable machine.

One test per decision primitive (Noul / Choice / Score), each asserting the full
Answer shape that primitive returns (https://docs.typesafe.ai/primitives). The
real-model server is loaded once via a module-scoped fixture and shared across
the three tests.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

from tests.conftest import serve
from whatdo.app import create_app

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def real_laya_client() -> Iterator[TypeSafeClient]:
    """The official SDK pointed at a server backed by the real Laya engine.

    Module-scoped so the checkpoint loads once for all three primitive tests.
    """
    pytest.importorskip("laya")
    from whatdo.inference.laya_engine import LayaEngine

    app = create_app(engine=LayaEngine())
    # A cold checkpoint load can be slow; give startup a generous window.
    with (
        serve(app, startup_timeout=600) as base_url,
        TypeSafeClient(api_key="test-key", base_url=base_url) as client,
    ):
        yield client


def test_noul_primitive_e2e(real_laya_client: TypeSafeClient) -> None:
    response = real_laya_client.system_one(
        state="I was charged twice. Please help.",
        questions={"billing": Noul(instructions="Is this about billing?")},
    )
    noul = response.nouls["billing"]
    # Noul returns a single calibrated probability and, unlike Choice/Score,
    # carries no confidence metric (primitives doc).
    assert 0.0 <= noul.noul <= 1.0
    assert not hasattr(noul, "confidence")
    assert response.usage.input_tokens is not None and response.usage.input_tokens > 0
    assert response.usage.output_tokens == 0


def test_choice_primitive_e2e(real_laya_client: TypeSafeClient) -> None:
    response = real_laya_client.system_one(
        state="This is outrageous — I want my money back right now!",
        questions={
            "tone": Choice(
                instructions="What is the tone?",
                criteria={"angry": None, "calm": None},
            )
        },
    )
    choice = response.choices["tone"]
    # Choice returns the selected option (from the set), a distribution over the
    # whole option set, and a confidence.
    assert choice.choice in {"angry", "calm"}
    assert 0.0 <= choice.confidence <= 1.0
    assert set(choice.probabilities) == {"angry", "calm"}
    assert abs(sum(choice.probabilities.values()) - 1.0) < 0.01


def test_score_primitive_e2e(real_laya_client: TypeSafeClient) -> None:
    response = real_laya_client.system_one(
        state="My house is on fire — I need help immediately!",
        questions={
            "urgency": Score(
                instructions="How urgent is this?",
                criteria=["low", "medium", "high"],
            )
        },
    )
    score = response.scores["urgency"]
    # Score returns a probability-weighted position over the rubric (may fall
    # between levels), a legend mapping levels to positions, the distribution,
    # and a confidence. The SDK coerces the string level keys to ints.
    assert 0.0 <= score.score <= 2.0
    assert 0.0 <= score.confidence <= 1.0
    assert set(score.legend) == {0, 1, 2}
    assert set(score.probabilities) == {0, 1, 2}
    assert abs(sum(score.probabilities.values()) - 1.0) < 0.01
