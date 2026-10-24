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
        assert data["provider"] in ("copilot_cli_fleet", "google_gemini_fleet")
        assert "healthy_keys" in data or "healthy_workers" in data


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


@pytest.mark.asyncio
async def test_qa_localsend_discover_endpoint(monkeypatch):
    from server.api import routes_qa

    monkeypatch.setattr(
        routes_qa,
        "_discover_localsend_peers_sync",
        lambda timeout_sec=1.5: [
            {
                "alias": "Aaradhya Phone",
                "host": "192.168.1.11",
                "port": 53317,
                "protocol": "http",
                "deviceModel": "Android",
                "deviceType": "mobile",
                "fingerprint": "fp-123",
            }
        ],
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/qa/localsend/discover?timeout=0.5")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["count"] == 1
        assert data["peers"][0]["alias"] == "Aaradhya Phone"
        assert data["peers"][0]["port"] == 53317


@pytest.mark.asyncio
async def test_qa_localsend_relay_fallback_when_no_peers(monkeypatch):
    from server.api import routes_qa

    monkeypatch.setattr(routes_qa, "_discover_localsend_peers_sync", lambda timeout_sec=1.5: [])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/qa/localsend/relay",
            json={
                "question": "What is 2 + 2?",
                "answer": "B) 4",
                "option_letter": "B",
                "confidence": 0.99,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert data["fallback"] == "pwa_route"


@pytest.mark.asyncio
async def test_qa_localsend_relay_success(monkeypatch):
    from server.api import routes_qa

    monkeypatch.setattr(
        routes_qa,
        "_probe_localsend_host_sync",
        lambda host, port=53317, protocol="http": {
            "alias": "Phone Receiver",
            "host": host,
            "port": port,
            "protocol": protocol,
        },
    )
    monkeypatch.setattr(
        routes_qa,
        "_send_localsend_payload_sync",
        lambda req, peer: {
            "ok": True,
            "mode": "text_preview_204",
            "peer": peer,
            "session_id": "",
            "bytes_sent": 128,
        },
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/qa/localsend/relay",
            json={
                "target_host": "192.168.1.11",
                "target_port": 53317,
                "protocol": "http",
                "question": "Nyquist rate for 4 kHz?",
                "answer": "C) 8 kHz",
                "option_letter": "C",
                "confidence": 0.98,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["mode"] == "text_preview_204"
        assert data["peer"]["host"] == "192.168.1.11"
