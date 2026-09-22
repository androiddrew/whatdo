"""With observability off, the server behaves identically and OTEL stays absent.

These run in the base install (no OTEL libraries): they must not import
opentelemetry, directly or transitively.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

from fastapi.testclient import TestClient

from whatdo.app import create_app
from whatdo.config import OtelSettings, Settings
from whatdo.observability import Telemetry

_BODY = {
    "state": "hi",
    "model": "jev-latest",
    "questions": {"q": {"type": "noul", "instructions": "billing?"}},
}


def test_default_settings_leave_observability_off() -> None:
    app = create_app()
    telemetry = app.state.telemetry
    assert isinstance(telemetry, Telemetry)
    # No provider is built when disabled.
    assert not hasattr(app.state, "otel_tracer_provider")
    assert not hasattr(app.state, "otel_meter_provider")


def test_request_succeeds_and_noop_telemetry_records_nothing() -> None:
    app = create_app(settings=Settings(otel=OtelSettings(enabled=False)))
    with TestClient(app) as client:
        response = client.post("/v1/systemone", json=_BODY)
    assert response.status_code == 200
    assert response.json()["answers"]["q"]["type"] == "noul"

    # The no-op facade tolerates every call without an exporter behind it.
    telemetry: Telemetry = app.state.telemetry
    telemetry.record_request(model="auto", question_count=1)
    telemetry.record_inference_latency(0.01)
    telemetry.record_overload()
    with telemetry.inference_span(model="auto", question_count=1) as span:
        assert span is None


def test_base_install_serves_with_opentelemetry_unimportable() -> None:
    # Prove criterion #1: with OTEL off, importing the app and serving a request
    # must not import opentelemetry. Run in a subprocess that blocks the import,
    # so this holds even though the dev venv happens to have the extra installed.
    script = textwrap.dedent(
        """
        import sys

        class _Blocker:
            def find_spec(self, name, path, target=None):
                if name == "opentelemetry" or name.startswith("opentelemetry."):
                    raise ImportError("opentelemetry blocked for base-install test")
                return None

        sys.meta_path.insert(0, _Blocker())

        from fastapi.testclient import TestClient
        from whatdo.app import create_app

        with TestClient(create_app()) as client:
            assert client.get("/healthz").status_code == 200
            response = client.post(
                "/v1/systemone",
                json={
                    "state": "hi",
                    "model": "jev-latest",
                    "questions": {"q": {"type": "noul", "instructions": "billing?"}},
                },
            )
            assert response.status_code == 200, response.status_code
        assert "opentelemetry" not in sys.modules
        print("OK")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
