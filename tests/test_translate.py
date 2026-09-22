"""Unit tests for the Jev <-> Laya translation (no laya/GPU needed)."""

from __future__ import annotations

from whatdo.inference.translate import to_jev_answer, to_laya_question
from whatdo.schemas.jev import (
    ChoiceAnswer,
    ChoiceQuestion,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)


def test_noul_question_to_laya_defaults_instructions() -> None:
    laya = to_laya_question(NoulQuestion())
    assert laya == {"type": "noul", "instructions": ""}


def test_noul_question_forwards_criteria() -> None:
    laya = to_laya_question(
        NoulQuestion(
            instructions="spam?",
            criteria={"true": "unsolicited ad", "false": "legit conversation"},
        )
    )
    assert laya == {
        "type": "noul",
        "instructions": "spam?",
        "criteria": {"true": "unsolicited ad", "false": "legit conversation"},
    }


def test_choice_question_to_laya_preserves_criteria() -> None:
    laya = to_laya_question(
        ChoiceQuestion(instructions="Tone?", criteria={"angry": None, "calm": "polite"})
    )
    assert laya == {
        "type": "choice",
        "instructions": "Tone?",
        "criteria": {"angry": None, "calm": "polite"},
    }


def test_score_question_to_laya_stringifies_levels() -> None:
    laya = to_laya_question(
        ScoreQuestion(instructions="Urgency?", criteria=["low", {"label": "high"}])
    )
    assert laya["type"] == "score"
    assert laya["criteria"] == ["low", '{"label": "high"}']


def test_laya_noul_answer_drops_action_and_confidence() -> None:
    answer = to_jev_answer(
        {"type": "noul", "noul": 0.9, "confidence": 0.9, "action": {"x": 1}}
    )
    assert isinstance(answer, NoulAnswer)
    assert answer.noul == 0.9


def test_laya_choice_answer_maps_fields() -> None:
    answer = to_jev_answer(
        {
            "type": "choice",
            "choice": "angry",
            "probabilities": {"angry": 0.8, "calm": 0.2},
            "confidence": 0.8,
            "action": {"act_probability": 0.5},
        }
    )
    assert isinstance(answer, ChoiceAnswer)
    assert answer.choice == "angry"
    assert answer.confidence == 0.8
    assert answer.probabilities == {"angry": 0.8, "calm": 0.2}


def test_laya_score_answer_maps_fields() -> None:
    answer = to_jev_answer(
        {
            "type": "score",
            "score": 1.7,
            "legend": {"0": "low", "1": "medium", "2": "high"},
            "probabilities": {"0": 0.1, "1": 0.1, "2": 0.8},
            "confidence": 0.8,
            "action": {},
        }
    )
    assert isinstance(answer, ScoreAnswer)
    assert answer.score == 1.7
    assert set(answer.legend) == {"0", "1", "2"}
