import pytest
import httpx
from client.adapters.lmstudio_local_adapter import LMStudioLocalAdapter


@pytest.mark.asyncio
async def test_lmstudio_adapter_health_success(monkeypatch):
    adapter = LMStudioLocalAdapter(worker_id="test_w", nickname="LMStudio Test")

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, json={"data": [{"id": "fleet-master-3b"}]})

    transport = httpx.MockTransport(mock_handler)
    real_client_cls = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client_cls(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    is_healthy = await adapter.check_health()
    assert is_healthy is True


@pytest.mark.asyncio
async def test_lmstudio_adapter_health_failure(monkeypatch):
    adapter = LMStudioLocalAdapter(worker_id="test_w", nickname="LMStudio Test")

    def mock_handler(request: httpx.Request):
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(mock_handler)
    real_client_cls = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client_cls(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    is_healthy = await adapter.check_health()
    assert is_healthy is False


@pytest.mark.asyncio
async def test_lmstudio_adapter_execute_task_success(monkeypatch):
    adapter = LMStudioLocalAdapter(worker_id="test_w", nickname="LMStudio Test", model="fleet-master-3b")

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "def solution(): pass"}}]
        })

    transport = httpx.MockTransport(mock_handler)
    real_client_cls = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client_cls(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    res = await adapter.execute_task("t1", "Write code", "code", {})
    assert res["success"] is True
    assert "def solution" in res["result_text"]
    assert res["error"] is None


@pytest.mark.asyncio
async def test_lmstudio_adapter_execute_task_error(monkeypatch):
    adapter = LMStudioLocalAdapter(worker_id="test_w", nickname="LMStudio Test")

    def mock_handler(request: httpx.Request):
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(mock_handler)
    real_client_cls = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client_cls(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    res = await adapter.execute_task("t1", "Write code", "code", {})
    assert res["success"] is False
    assert "HTTP 500" in res["error"]
