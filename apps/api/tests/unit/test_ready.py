from fastapi.testclient import TestClient

from evercurrent.main import app


def test_ready_returns_ok_with_dependency_checks() -> None:
    # When the DB is reachable /ready reports {"db": "ok"}; in unit-test
    # context (no Postgres) the probe is suppressed and stays "skipped".
    # Either way the response is 200 and well-shaped.
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["checks"].keys()) == {"db", "redis"}
    assert body["checks"]["db"] in {"ok", "skipped"}
    assert body["checks"]["redis"] == "skipped"
