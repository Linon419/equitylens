from fastapi.testclient import TestClient

from app.app import app

client = TestClient(app)


def test_liveness() -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_exposes_active_profile() -> None:
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "deployment_target": "docker",
    }
