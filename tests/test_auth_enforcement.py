from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from server.core.config import settings
from server.core.database import init_db
from server.main import MCPAuthMiddleware, app

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_auth.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", test_db)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    await init_db()
    yield

@pytest.mark.asyncio
async def test_auth_allowed_in_dev_mode_when_no_key_configured(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "API_AUTH_KEY", "")
    monkeypatch.setattr(settings, "ALLOW_ANONYMOUS_DEV", True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /api/v1/jobs
        resp = await client.get("/api/v1/jobs")
        assert resp.status_code == 200

        # GET /api/v1/tasks
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 200

        # GET /api/v1/workers
        resp = await client.get("/api/v1/workers")
        assert resp.status_code == 200

        # GET /api/v1/memory
        resp = await client.get("/api/v1/memory")
        assert resp.status_code == 200

@pytest.mark.asyncio
async def test_auth_enforced_when_api_key_configured(monkeypatch):
    dummy_auth_val = "x" * 32
    monkeypatch.setattr(settings, "API_AUTH_KEY", dummy_auth_val)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unauthenticated calls MUST return 401 (including MCP SSE mount)
        for endpoint in ["/api/v1/jobs", "/api/v1/tasks", "/api/v1/workers", "/api/v1/memory", "/mcp/"]:
            unauth = await client.get(endpoint)
            assert unauth.status_code == 401, f"Expected 401 for {endpoint}, got {unauth.status_code}"

        # Invalid token MUST return 401
        invalid = await client.get("/api/v1/jobs", headers={"Authorization": "Bearer invalid-bearer-value"})
        assert invalid.status_code == 401
        conflicting_api = await client.get(
            "/api/v1/jobs",
            headers={"Authorization": "Bearer wrong_key", "X-API-Key": dummy_auth_val},
        )
        assert conflicting_api.status_code == 401

        invalid_mcp = await client.get("/mcp/", headers={"X-API-Key": "wrong_key"})
        assert invalid_mcp.status_code == 401
        invalid_mcp_bearer = await client.get("/mcp/", headers={"Authorization": "Bearer wrong_key"})
        assert invalid_mcp_bearer.status_code == 401
        assert "wrong_key" not in invalid_mcp_bearer.text
        conflicting_mcp = await client.get(
            "/mcp/",
            headers={"Authorization": "Bearer wrong_key", "X-API-Key": dummy_auth_val},
        )
        assert conflicting_mcp.status_code == 401

        # Valid Bearer token MUST succeed
        valid_bearer = await client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {dummy_auth_val}"})
        assert valid_bearer.status_code == 200

        # Valid X-API-Key header MUST succeed
        valid_header = await client.get("/api/v1/tasks", headers={"X-API-Key": dummy_auth_val})
        assert valid_header.status_code == 200

        # Query-string auth MUST be rejected on MCP endpoint (G-3 hardening)
        query_auth_mcp = await client.post(f"/mcp/messages/?api_key={dummy_auth_val}")
        assert query_auth_mcp.status_code == 401, "Query string credentials must be rejected to prevent log leakage"

        # Valid MCP header auth passes through the middleware into the SSE app (returning 400 Bad Request instead of 401)
        valid_mcp = await client.post("/mcp/messages/", headers={"X-API-Key": dummy_auth_val})
        assert valid_mcp.status_code != 401, f"Expected authenticated MCP call to pass middleware, got {valid_mcp.status_code}"
        valid_mcp_bearer = await client.post(
            "/mcp/messages/",
            headers={"Authorization": "Bearer " + dummy_auth_val},
        )
        assert valid_mcp_bearer.status_code != 401


@pytest.mark.asyncio
async def test_auth_rejects_anonymous_in_production_even_if_no_key(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "API_AUTH_KEY", "")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/jobs")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_rejects_anonymous_in_dev_when_allow_anonymous_disabled(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "API_AUTH_KEY", "")
    monkeypatch.setattr(settings, "ALLOW_ANONYMOUS_DEV", False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/jobs")
        assert resp.status_code == 401


@pytest.mark.parametrize(
    ("environment", "allow_anonymous", "expected_status"),
    [
        ("production", True, 401),
        ("development", False, 401),
        ("development", True, 204),
    ],
)
@pytest.mark.asyncio
async def test_mcp_asgi_middleware_applies_empty_key_policy(
    monkeypatch, environment, allow_anonymous, expected_status
):
    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    monkeypatch.setattr(settings, "API_AUTH_KEY", "")
    monkeypatch.setattr(settings, "ALLOW_ANONYMOUS_DEV", allow_anonymous)

    async def downstream_app(scope, receive, send):
        from starlette.responses import Response

        await Response(status_code=204)(scope, receive, send)

    transport = ASGITransport(app=MCPAuthMiddleware(downstream_app))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/mcp/")

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("header_name", "header_values", "expected_rejection"),
    [
        ("Authorization", ("Bearer " + "x" * 32, "Bearer invalid"), False),
        ("Authorization", ("Bearer invalid", "Bearer " + "x" * 32), True),
        ("X-API-Key", ("x" * 32, "invalid"), False),
        ("X-API-Key", ("invalid", "x" * 32), True),
    ],
)
@pytest.mark.asyncio
async def test_duplicate_auth_headers_have_consistent_rest_and_mcp_policy(
    monkeypatch, header_name, header_values, expected_rejection
):
    monkeypatch.setattr(settings, "API_AUTH_KEY", "x" * 32)
    headers = [(header_name, value) for value in header_values]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rest_response = await client.get("/api/v1/jobs", headers=headers)
        mcp_response = await client.post("/mcp/messages/", headers=headers)

    assert (rest_response.status_code == 401) is expected_rejection
    assert (mcp_response.status_code == 401) is expected_rejection
