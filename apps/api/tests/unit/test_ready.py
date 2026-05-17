from fastapi.testclient import TestClient

from evercurrent.main import app


def test_ready_returns_ok_with_skipped_dependency_checks() -> None:
    # Until DB + Redis clients are wired through FastAPI lifespan, /ready
    # reports the dependency checks as "skipped" rather than probing them.
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"db": "skipped", "redis": "skipped"}
