from fastapi.testclient import TestClient

from app.main import app


def test_unknown_route_returns_typed_404_envelope():
    with TestClient(app) as client:
        response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert set(body.keys()) == {"code", "message", "details", "evidence"}
    assert body["code"] == "HTTP_404"


def test_bad_query_param_returns_typed_422_envelope():
    # /healthz takes no params, so hit a route via an invalid method-shaped
    # request is awkward without a body-accepting route; instead exercise the
    # validation handler contract directly against a minimal throwaway route.
    from fastapi import FastAPI
    from fastapi.exceptions import RequestValidationError
    from pydantic import BaseModel

    from app.core.errors import validation_error_handler

    probe = FastAPI()
    probe.add_exception_handler(RequestValidationError, validation_error_handler)

    class Payload(BaseModel):
        name: str

    @probe.post("/probe")
    def probe_route(payload: Payload) -> dict:
        return {"ok": True}

    with TestClient(probe) as client:
        response = client.post("/probe", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "errors" in body["details"]
