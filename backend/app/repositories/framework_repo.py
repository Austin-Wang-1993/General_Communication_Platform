"""`framework.json` 读写。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.repositories.base import read_json, write_json_atomic


class FrameworkRepo:
    def __init__(self, data_dir: Path) -> None:
        self._scenarios = data_dir / "scenarios"

    def _path(self, scenario_id: str) -> Path:
        return self._scenarios / scenario_id / "framework.json"

    async def save(self, scenario_id: str, document: dict[str, Any]) -> None:
        await write_json_atomic(self._path(scenario_id), document)

    async def load_raw(self, scenario_id: str) -> dict[str, Any] | None:
        data = await read_json(self._path(scenario_id))
        return data if isinstance(data, dict) else None
