"""M0 健康检查端点测试。

运行：cd backend && pytest -q
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(app_client: TestClient) -> None:
    response = app_client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload["ok"] is True
    assert payload["service"] == "gcp-backend"
    assert payload["version"]
    assert payload["server_time"].endswith("Z")
    assert isinstance(payload["data_dir_writable"], bool)
    assert isinstance(payload["deepseek_configured"], bool)
