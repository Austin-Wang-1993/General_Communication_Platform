"""英译中句级辅助（中台 §6.9）：不读写场景包、不触碰 turns。"""

from __future__ import annotations

from app.clients.llm_client import LlmClient
from app.errors import ContentEmptyOrTooLongError


class TranslationService:
    def __init__(self, *, llm_client: LlmClient) -> None:
        self._llm = llm_client

    async def translate_en_to_zh(self, text: str) -> str:
        raw = text.strip()
        if not raw:
            raise ContentEmptyOrTooLongError(details={"field": "text"})
        if len(raw) > 8000:
            raise ContentEmptyOrTooLongError(details={"field": "text", "length": len(raw)})
        return await self._llm.translate_line_en_to_zh(source_text=raw)
