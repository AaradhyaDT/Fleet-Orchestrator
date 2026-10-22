import pytest
from httpx import AsyncClient, ASGITransport
from server.main import app

@pytest.mark.asyncio
async def test_lens_pwa_served():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/lens")
        assert response.status_code == 200
        assert "Screen Lens" in response.text
        assert "shutterBtn" in response.text

@pytest.mark.asyncio
async def test_qa_status_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/qa/status")
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "google_gemini_fleet"
        assert "healthy_keys" in data
