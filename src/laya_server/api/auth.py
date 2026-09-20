"""Bearer-token authentication for the Jev API.

Two postures (ticket #6): when ``LAYA_AUTH__ENABLED`` is false the dependency is
never applied — the app factory simply omits it, so requests are accepted with
no ``Authorization`` header. When enabled, the ``Authorization: Bearer <token>``
header is validated in constant time against the configured ``api_keys``; a
missing, malformed, or unknown token yields a 401 in the Jev error envelope
(``{"detail": ...}``, the same shape the official SDK reads).

There is no rate-limiting / 429 here; overload backpressure is ADR-0003's 529.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from laya_server.api.dependencies import get_settings
from laya_server.config import Settings

_BEARER_PREFIX = "Bearer "


def _unauthorized(detail: str) -> HTTPException:
    # WWW-Authenticate: Bearer is the RFC 6750 challenge for a protected resource.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _token_is_accepted(token: str, api_keys: list[str]) -> bool:
    """Whether ``token`` matches any configured key, compared in constant time.

    Every key is checked with ``secrets.compare_digest`` (no early byte-wise
    exit) so a matching prefix is not distinguishable by timing. ``matched`` is
    or-accumulated rather than returned early so a present key and an absent one
    take the same number of comparisons.
    """
    # Compare bytes, not str: secrets.compare_digest rejects non-ASCII str with a
    # TypeError, which would surface as a 500 for a token like "café" instead of
    # the 401 an invalid token must get.
    token_bytes = token.encode()
    matched = False
    for key in api_keys:
        if secrets.compare_digest(token_bytes, key.encode()):
            matched = True
    return matched


def require_api_key(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Reject the request unless it carries a valid bearer token.

    Applied only when auth is enabled; see the module docstring and the app
    factory. Raises 401 on a missing/malformed header or an unknown token.
    """
    header = request.headers.get("Authorization")
    if header is None or not header.startswith(_BEARER_PREFIX):
        raise _unauthorized("Missing or malformed bearer token.")

    token = header[len(_BEARER_PREFIX) :]
    if not _token_is_accepted(token, settings.auth.api_keys):
        raise _unauthorized("Invalid API key.")
