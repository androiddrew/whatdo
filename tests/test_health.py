from fastapi.testclient import TestClient

from whatdo.app import create_app
from whatdo.inference.fake import FakeEngine


def test_healthz_returns_ok() -> None:
    with TestClient(create_app(engine=FakeEngine())) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
