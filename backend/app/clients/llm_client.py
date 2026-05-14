"""DeepSeek Chat Completions 客户端（技术方案 §3 / OpenAI 兼容接口）。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings
from app.errors import LlmFailureError, LlmTimeoutError

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "intake.md"


def load_intake_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


class LlmClient:
    """封装 `chat/completions` + `response_format: json_object`。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._system_prompt = load_intake_system_prompt()

    async def expand_intake(
        self,
        *,
        snapshot: dict[str, str],
        repair_hint: str | None = None,
        temperature: float = 0.6,
    ) -> dict[str, Any]:
        if not self._settings.deepseek_api_key:
            raise LlmFailureError(
                message="未配置 DeepSeek API Key",
                details={"hint": "设置环境变量 DEEPSEEK_API_KEY"},
            )

        payload: dict[str, Any] = {"intake_snapshot": snapshot}
        if repair_hint:
            payload["repair_instruction"] = repair_hint

        user_content = json.dumps(payload, ensure_ascii=False)
        body: dict[str, Any] = {
            "model": self._settings.deepseek_model,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
        }

        base = self._settings.deepseek_base_url.rstrip("/")
        url = f"{base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(120.0, connect=15.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as e:
            raise LlmTimeoutError(details={"reason": str(e)}) from e
        except httpx.RequestError as e:
            raise LlmFailureError(
                message="无法连接语言模型服务",
                details={"reason": str(e)},
            ) from e

        if resp.status_code >= 400:
            raise LlmFailureError(
                message="语言模型返回错误状态",
                details={"status_code": resp.status_code, "body": resp.text[:2000]},
            )

        try:
            envelope = resp.json()
            content = envelope["choices"][0]["message"]["content"]
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise LlmFailureError(
                message="语言模型响应结构异常",
                details={"reason": str(e), "raw": resp.text[:2000]},
            ) from e

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise LlmFailureError(
                message="语言模型未返回合法 JSON",
                details={"reason": str(e), "content_preview": content[:2000]},
            ) from e
