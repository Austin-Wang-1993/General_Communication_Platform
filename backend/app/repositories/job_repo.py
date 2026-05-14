"""创作 Job 状态文件（`data/scenarios/{id}/jobs/{job_id}.json`）。"""

from __future__ import annotations

import json
from pathlib import Path

from app.models.creation_jobs import JobRecord, JobStatus
from app.repositories.base import read_json, write_json_atomic


class JobRepo:
    def __init__(self, data_dir: Path) -> None:
        self._scenarios = data_dir / "scenarios"

    def _jobs_dir(self, scenario_id: str) -> Path:
        return self._scenarios / scenario_id / "jobs"

    def _path(self, scenario_id: str, job_id: str) -> Path:
        return self._jobs_dir(scenario_id) / f"{job_id}.json"

    async def save(self, record: JobRecord) -> None:
        await write_json_atomic(
            self._path(record.scenario_id, record.job_id),
            record.model_dump(mode="json"),
        )

    async def load(self, scenario_id: str, job_id: str) -> JobRecord | None:
        data = await read_json(self._path(scenario_id, job_id))
        if data is None:
            return None
        return JobRecord.model_validate(data)

    async def has_active_job(self, scenario_id: str) -> bool:
        """存在 `queued` / `running` 的 Job 即视为冲突。"""
        jdir = self._jobs_dir(scenario_id)
        if not jdir.exists():
            return False

        def _scan() -> bool:
            for p in jdir.glob("*.json"):
                try:
                    raw = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(raw, dict):
                    continue
                st = raw.get("status")
                if st in (JobStatus.QUEUED.value, JobStatus.RUNNING.value):
                    return True
            return False

        import asyncio

        return await asyncio.to_thread(_scan)
