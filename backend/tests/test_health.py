from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings


def test_health_ok_without_llm_key(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "MediSimplify"
    assert body["environment"] == "test"
    assert body["llm"]["provider"] == "gemini"
    assert body["llm"]["api_key_configured"] is False
    assert body["limits"]["max_upload_mb"] == 10


def test_health_reports_key_presence_without_leaking_it() -> None:
    secret = "test-key-do-not-leak-123"
    client = TestClient(create_app(make_settings(gemini_api_key=secret)))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["llm"]["api_key_configured"] is True
    assert secret not in response.text


def test_cors_allows_configured_frontend_origin(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": "http://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_unknown_route_returns_uniform_error(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"code": "http_404", "message": "Not Found"}
