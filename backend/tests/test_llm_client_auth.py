"""LlmClient 对上游鉴权错误的映射（401/403 → llm_authentication_failed）。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.clients.llm_client import LlmClient
from app.config import Settings
from app.errors import LlmAuthenticationError


class _Stub401Client:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, *args, **kwargs):
        class R:
            status_code = 401
            text = '{"error":{"message":"invalid"}}'

        return R()


@pytest.mark.asyncio
async def test_expand_intake_maps_upstream_401() -> None:
    settings = Settings(deepseek_api_key="sk-test")
    llm = LlmClient(settings)
    with patch("app.clients.llm_client.httpx.AsyncClient", return_value=_Stub401Client()):
        with pytest.raises(LlmAuthenticationError):
            await llm.expand_intake(snapshot={"scenario_title": "t"})


def test_deepseek_api_key_trimmed_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "  sk-example  \n")
    from app import config as config_module

    config_module._settings = None  # type: ignore[attr-defined]
    from app.config import get_settings

    assert get_settings().deepseek_api_key == "sk-example"
    config_module._settings = None  # type: ignore[attr-defined]

