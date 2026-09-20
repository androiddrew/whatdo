"""Contract tests: the real Typesafe SDK against both auth postures.

Complements ``test_contract_system_one.py`` (which covers the no-auth happy
path). Here the official ``typesafe-sdk-python`` — the same client operators use
— proves that auth mode accepts a valid key and rejects an invalid one with the
401 the SDK surfaces as ``TypeSafeAuthenticationError``, and that no-auth mode
accepts a request regardless of the key sent.
"""

from __future__ import annotations

import pytest
from typesafe_sdk import Noul, TypeSafeAuthenticationError, TypeSafeClient

from tests.conftest import AUTH_API_KEY

_QUESTIONS = {"billing": Noul(instructions="Is this about billing?")}


def _client(base_url: str, api_key: str) -> TypeSafeClient:
    return TypeSafeClient(api_key=api_key, base_url=base_url)


def test_auth_mode_accepts_valid_key(auth_live_server: str) -> None:
    with _client(auth_live_server, AUTH_API_KEY) as client:
        response = client.system_one(state="charged twice", questions=_QUESTIONS)
    assert 0.0 <= response.nouls["billing"].noul <= 1.0


def test_auth_mode_rejects_invalid_key(auth_live_server: str) -> None:
    with (
        _client(auth_live_server, "wrong-key") as client,
        pytest.raises(TypeSafeAuthenticationError) as excinfo,
    ):
        client.system_one(state="charged twice", questions=_QUESTIONS)
    assert excinfo.value.status == 401


def test_no_auth_mode_accepts_any_key(sdk_client: TypeSafeClient) -> None:
    # `sdk_client` targets the no-auth live server with an arbitrary key; the
    # request must succeed because the auth dependency is never applied.
    response = sdk_client.system_one(state="charged twice", questions=_QUESTIONS)
    assert 0.0 <= response.nouls["billing"].noul <= 1.0
