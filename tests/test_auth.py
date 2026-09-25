"""Wire-level auth behaviour for the Jev API (no SDK).

These drive the endpoints directly to assert both auth postures: the dependency
is absent entirely when auth is disabled, and enforced (401 in the Jev error
envelope) when enabled. The real-SDK view of the same behaviour lives in
``test_contract_auth.py``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from whatdo.app import create_app
from whatdo.config import AuthSettings, Settings
from whatdo.inference.fake import FakeEngine

_VALID_KEY = "s3cret-key"
_OTHER_KEY = "second-key"


def _auth_client() -> TestClient:
    """A client for a server with auth enabled and two configured keys."""
    settings = Settings(
        auth=AuthSettings(enabled=True, api_keys=[_VALID_KEY, _OTHER_KEY])
    )
    return TestClient(create_app(settings=settings, engine=FakeEngine()))


def _noauth_client() -> TestClient:
    """A client for a server with auth disabled."""
    settings = Settings(auth=AuthSettings(enabled=False))
    return TestClient(create_app(settings=settings, engine=FakeEngine()))


_BODY = {
    "state": "hi",
    "model": "jev-latest",
    "questions": {"q": {"type": "noul", "instructions": "billing?"}},
}


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auth_disabled_accepts_request_without_header() -> None:
    with _noauth_client() as client:
        response = client.post("/v1/systemone", json=_BODY)
    assert response.status_code == 200


def test_auth_enabled_accepts_valid_bearer_token() -> None:
    with _auth_client() as client:
        response = client.post("/v1/systemone", json=_BODY, headers=_bearer(_VALID_KEY))
    assert response.status_code == 200


def test_auth_enabled_accepts_any_configured_key() -> None:
    with _auth_client() as client:
        response = client.post("/v1/systemone", json=_BODY, headers=_bearer(_OTHER_KEY))
    assert response.status_code == 200


def test_auth_enabled_rejects_missing_header() -> None:
    with _auth_client() as client:
        response = client.post("/v1/systemone", json=_BODY)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert isinstance(response.json()["detail"], str)


def test_auth_enabled_rejects_invalid_token() -> None:
    with _auth_client() as client:
        response = client.post(
            "/v1/systemone", json=_BODY, headers=_bearer("not-the-key")
        )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_auth_enabled_rejects_non_ascii_token() -> None:
    # A raw non-ASCII header byte decodes server-side to a non-ASCII str, which
    # secrets.compare_digest rejects with a TypeError; that must still resolve to
    # a clean 401, never an unhandled 500. Sent as bytes because an HTTP client
    # will not encode a non-ASCII str header at all.
    with _auth_client() as client:
        response = client.post(
            "/v1/systemone",
            json=_BODY,
            headers={"Authorization": "Bearer café".encode("latin-1")},
        )
    assert response.status_code == 401


def test_auth_enabled_rejects_non_bearer_scheme() -> None:
    with _auth_client() as client:
        response = client.post(
            "/v1/systemone",
            json=_BODY,
            headers={"Authorization": f"Basic {_VALID_KEY}"},
        )
    assert response.status_code == 401


def test_auth_enabled_also_protects_models_listing() -> None:
    with _auth_client() as client:
        missing = client.get("/v1/models")
        valid = client.get("/v1/models", headers=_bearer(_VALID_KEY))
    assert missing.status_code == 401
    assert valid.status_code == 200


def test_health_endpoints_never_require_auth() -> None:
    with _auth_client() as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200
