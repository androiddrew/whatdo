"""Contract test: the real Typesafe SDK against our server (with FakeEngine).

This proves the core project goal — the official `typesafe-sdk-python`, pointed
at this server via TYPESAFE_BASE_URL, gets a valid Jev response it can parse.
"""

from __future__ import annotations

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient


def test_system_one_round_trips_through_the_official_sdk(
    sdk_client: TypeSafeClient,
) -> None:
    response = sdk_client.system_one(
        state={"message": "I was charged twice. Please help."},
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

    # jev-latest resolves to the default served model "auto" (ADR-0004 shim).
    assert response.model == "auto"
    assert set(response.answers) == {"billing", "tone", "urgency"}

    noul = response.nouls["billing"]
    assert 0.0 <= noul.noul <= 1.0

    choice = response.choices["tone"]
    assert choice.choice in {"angry", "calm"}
    assert 0.0 <= choice.confidence <= 1.0
    assert set(choice.probabilities) == {"angry", "calm"}

    score = response.scores["urgency"]
    assert 0.0 <= score.score <= 2.0
    assert set(score.legend) == {0, 1, 2}  # SDK coerces string keys to ints
    assert set(score.probabilities) == {0, 1, 2}

    assert response.usage.input_tokens is not None
    assert response.usage.output_tokens == 0


def test_system_one_is_deterministic(sdk_client: TypeSafeClient) -> None:
    questions = {"billing": Noul(instructions="Is this about billing?")}
    first = sdk_client.system_one(state="charged twice", questions=questions)
    second = sdk_client.system_one(state="charged twice", questions=questions)

    assert first.nouls["billing"].noul == second.nouls["billing"].noul
