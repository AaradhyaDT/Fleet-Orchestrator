"""
test_quota_dashboard_api.py
---------------------------
Tests for the /workers/quota-dashboard FastAPI endpoint.
"""

from pathlib import Path
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from server.core.config import settings
from server.core.database import init_db
from server.main import app


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_PATH", tmp_path / "dashboard_test.db")
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "API_AUTH_KEY", "test-auth-key-123")
    await init_db()


@pytest.mark.asyncio
async def test_quota_dashboard_api_endpoint():
    transport = ASGITransport(app=app)
    headers = {"X-API-Key": "test-auth-key-123"}

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Unauthenticated request should return 401
        url = f"{settings.API_V1_STR}/workers/quota-dashboard"
        unauth = await client.get(url)
        assert unauth.status_code == 401

        # 2. Authenticated request should return 200 with fleet metrics
        resp = await client.get(url, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "fleet" in data
        assert "workers" in data
        assert "tasks" in data
        assert data["fleet"]["total_monthly_credits"] >= 200
        assert "burn_rate_pct" in data["fleet"]
