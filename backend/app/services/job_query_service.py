"""Job 轮询查询（API §3.3），与具体 Job 类型解耦。"""

from __future__ import annotations

from app.errors import JobNotFoundError
from app.models.creation_jobs import JobPollResponse
from app.repositories.job_repo import JobRepo


class JobQueryService:
    def __init__(self, *, job_repo: JobRepo) -> None:
        self.job_repo = job_repo

    async def get_job(self, scenario_id: str, job_id: str) -> JobPollResponse:
        rec = await self.job_repo.load(scenario_id, job_id)
        if rec is None or rec.scenario_id != scenario_id:
            raise JobNotFoundError(details={"scenario_id": scenario_id, "job_id": job_id})
        return JobPollResponse.model_validate(rec.model_dump(mode="json"))
