from fastapi.testclient import TestClient

from app.main import app


def test_healthz_returns_ok():
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_returns_build_metadata():
    with TestClient(app) as client:
        response = client.get("/version")
    assert response.status_code == 200
    body = response.json()
    assert "version" in body
    assert "git_sha" in body


def test_cors_header_present_for_allowed_origin():
    with TestClient(app) as client:
        response = client.get("/healthz", headers={"origin": "http://localhost:5173"})
    assert (
        response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    )


def test_correlation_id_header_present_on_response():
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert "x-correlation-id" in response.headers
