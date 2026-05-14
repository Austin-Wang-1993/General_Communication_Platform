"""本节最新回答提示 `hint_latest.json`（API §5.2）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.lib.clock import utc_now_rfc3339
from app.repositories.base import read_json, write_json_atomic


class HintsRepo:
    def __init__(self, data_dir: Path) -> None:
        self._scenarios = data_dir / "scenarios"

    def hint_path(self, scenario_id: str, chapter_id: int, section_id: int) -> Path:
        return (
            self._scenarios
            / scenario_id
            / "sections"
            / f"ch{chapter_id}_sec{section_id}"
            / "hint_latest.json"
        )

    async def load_latest(self, scenario_id: str, chapter_id: int, section_id: int) -> dict[str, Any] | None:
        path = self.hint_path(scenario_id, chapter_id, section_id)
        raw = await read_json(path)
        return raw if isinstance(raw, dict) else None

    async def save_latest(
        self,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
        data: dict[str, Any],
    ) -> None:
        await write_json_atomic(self.hint_path(scenario_id, chapter_id, section_id), data)

    async def mark_stale_if_ready(self, scenario_id: str, chapter_id: int, section_id: int) -> None:
        """用户发出新回合后，将上一份 ready 提示置为 stale（PRD §6.7.4）。"""
        raw = await self.load_latest(scenario_id, chapter_id, section_id)
        if not raw or raw.get("hint_status") != "ready":
            return
        raw["hint_status"] = "stale"
        raw["analysis_markdown"] = ""
        raw["suggested_utterances"] = []
        raw["generated_at"] = utc_now_rfc3339()
        await self.save_latest(scenario_id, chapter_id, section_id, raw)
