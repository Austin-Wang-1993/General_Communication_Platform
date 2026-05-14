"""本节复盘 `analytics.json`（API §6.1，PRD §6.8）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.repositories.base import read_json, write_json_atomic


class SectionAnalyticsRepo:
    def __init__(self, data_dir: Path) -> None:
        self._scenarios = data_dir / "scenarios"

    def analytics_path(self, scenario_id: str, chapter_id: int, section_id: int) -> Path:
        return (
            self._scenarios
            / scenario_id
            / "sections"
            / f"ch{chapter_id}_sec{section_id}"
            / "analytics.json"
        )

    async def load(self, scenario_id: str, chapter_id: int, section_id: int) -> dict[str, Any] | None:
        path = self.analytics_path(scenario_id, chapter_id, section_id)
        raw = await read_json(path)
        return raw if isinstance(raw, dict) else None

    async def save(self, scenario_id: str, chapter_id: int, section_id: int, data: dict[str, Any]) -> None:
        await write_json_atomic(self.analytics_path(scenario_id, chapter_id, section_id), data)
