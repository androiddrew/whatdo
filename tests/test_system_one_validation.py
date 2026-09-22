"""Wire-level validation and edge behaviour for POST /v1/systemone.

These drive the endpoint directly (no SDK) to assert the Jev-compatible 422
shape, forward-compat handling of extra top-level fields, and readiness.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from whatdo.app import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_unknown_question_type_is_422() -> None:
    with _client() as client:
        response = client.post(
            "/v1/systemone",
            json={
                "state": "hi",
                "model": "jev-latest",
                "questions": {"q": {"type": "bogus", "instructions": "?"}},
            },
        )
    assert response.status_code == 422
    assert "detail" in response.json()  # Jev-compatible validation shape


def test_score_with_empty_criteria_is_422() -> None:
    with _client() as client:
        response = client.post(
            "/v1/systemone",
            json={
                "state": "hi",
                "model": "jev-latest",
                "questions": {"urgency": {"type": "score", "criteria": []}},
            },
        )
    assert response.status_code == 422


def test_unknown_field_inside_a_question_is_422() -> None:
    with _client() as client:
        response = client.post(
            "/v1/systemone",
            json={
                "state": "hi",
                "model": "jev-latest",
                "questions": {"q": {"type": "noul", "surprise": 1}},
            },
        )
    assert response.status_code == 422


def test_missing_state_is_422() -> None:
    with _client() as client:
        response = client.post(
            "/v1/systemone",
            json={"model": "jev-latest", "questions": {"q": {"type": "noul"}}},
        )
    assert response.status_code == 422


def test_empty_questions_is_422() -> None:
    with _client() as client:
        response = client.post(
            "/v1/systemone",
            json={"state": "hi", "model": "jev-latest", "questions": {}},
        )
    assert response.status_code == 422


def test_unknown_top_level_field_is_ignored() -> None:
    with _client() as client:
        response = client.post(
            "/v1/systemone",
            json={
                "state": "hi",
                "model": "jev-latest",
                "questions": {"q": {"type": "noul", "instructions": "spam?"}},
                "future_field": {"anything": True},
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["answers"]["q"]["type"] == "noul"
    assert body["usage"]["output_tokens"] == 0


def test_readyz_is_ready() -> None:
    with _client() as client:
        response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
