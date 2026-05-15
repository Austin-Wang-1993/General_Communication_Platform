"""本节对话回合 `turns.jsonl`（技术方案 §5：`sections/ch*_sec*/turns.jsonl`）。"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from app.errors import RepositoryIoError


class TurnsRepo:
    def __init__(self, data_dir: Path) -> None:
        self._scenarios = data_dir / "scenarios"

    def turns_path(self, scenario_id: str, chapter_id: int, section_id: int) -> Path:
        return (
            self._scenarios
            / scenario_id
            / "sections"
            / f"ch{chapter_id}_sec{section_id}"
            / "turns.jsonl"
        )

    async def read_all(
        self,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        path = self.turns_path(scenario_id, chapter_id, section_id)

        def _read() -> list[dict[str, Any]]:
            if not path.exists():
                return []
            out: list[dict[str, Any]] = []
            try:
                with path.open(encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        out.append(json.loads(line))
            except Exception as e:
                raise RepositoryIoError(
                    message="读取 turns.jsonl 失败",
                    details={"path": str(path), "error": str(e)},
                ) from e
            if limit is not None and limit > 0 and len(out) > limit:
                return out[-limit:]
            return out

        return await asyncio.to_thread(_read)

    async def append(self, scenario_id: str, chapter_id: int, section_id: int, turn: dict[str, Any]) -> None:
        path = self.turns_path(scenario_id, chapter_id, section_id)
        line = json.dumps(turn, ensure_ascii=False) + "\n"

        def _append() -> None:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as f:
                    f.write(line)
            except Exception as e:
                raise RepositoryIoError(
                    message="追加 turns.jsonl 失败",
                    details={"path": str(path), "error": str(e)},
                ) from e

        await asyncio.to_thread(_append)

    async def pop_last_turn_if_turn_id(
        self,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
        *,
        turn_id: str,
    ) -> bool:
        """若 `turns.jsonl` 末行 JSON 的 `turn_id` 与参数一致则删除该行并覆写文件。

        用于在用户发言已落盘但 NPC 续写失败时回滚，避免「用户独白」卡死运行态。
        """

        path = self.turns_path(scenario_id, chapter_id, section_id)

        def _pop() -> bool:
            if not path.exists():
                return False
            try:
                lines: list[str] = []
                with path.open(encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            lines.append(line.rstrip("\n"))
                if not lines:
                    return False
                last_obj = json.loads(lines[-1])
                if not isinstance(last_obj, dict) or str(last_obj.get("turn_id", "")) != turn_id:
                    return False
                lines.pop()
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(path.suffix + ".tmp")
                with tmp.open("w", encoding="utf-8") as wf:
                    for raw in lines:
                        wf.write(raw + "\n")
                os.replace(tmp, path)
                return True
            except Exception as e:
                raise RepositoryIoError(
                    message="回滚 turns.jsonl 末行失败",
                    details={"path": str(path), "error": str(e)},
                ) from e

        return await asyncio.to_thread(_pop)
