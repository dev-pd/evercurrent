from fastapi.testclient import TestClient

from evercurrent.main import app


def test_ready_returns_ok_with_dependency_checks() -> None:
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["checks"].keys()) == {"db", "redis"}
    assert body["checks"]["db"] in {"ok", "skipped"}
    assert body["checks"]["redis"] == "skipped"
