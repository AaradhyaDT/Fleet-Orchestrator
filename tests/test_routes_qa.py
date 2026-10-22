import pytest
from httpx import AsyncClient, ASGITransport
from server.main import app
from server.api.routes_qa import broadcast_qa_update


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


@pytest.mark.asyncio
async def test_qa_latest_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/qa/latest")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


@pytest.mark.asyncio
async def test_qa_broadcast_and_latest():
    broadcast_qa_update({
        "id": 999999,
        "timestamp": 123456789.0,
        "question": "What is the time complexity of QuickSort average case?",
        "option_letter": "B",
        "reason": "Average case is O(n log n)",
        "answer": "B. O(n log n)",
        "confidence": 0.96,
        "mode": "fast_hud",
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/qa/latest")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["option_letter"] == "B"
        assert data["reason"] == "Average case is O(n log n)"
