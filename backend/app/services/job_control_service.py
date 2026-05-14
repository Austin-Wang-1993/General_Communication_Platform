"""Job 取消（API §3.4）。"""

from __future__ import annotations

from app.errors import JobAlreadyTerminalError, JobNotFoundError, ScenarioNotFoundError
from app.lib.clock import utc_now_rfc3339
from app.models.creation_jobs import CancelJobResponse, JobStatus, JobType
from app.models.enums import LifecyclePhase
from app.repositories.base import get_scenario_lock, remove_dir_tree
from app.repositories.job_repo import JobRepo
from app.repositories.package_repo import PackageRepo


class JobControlService:
    def __init__(self, *, package_repo: PackageRepo, job_repo: JobRepo) -> None:
        self.package_repo = package_repo
        self.job_repo = job_repo

    async def cancel_job(self, scenario_id: str, job_id: str) -> CancelJobResponse:
        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is None:
                raise ScenarioNotFoundError(details={"scenario_id": scenario_id})
            job = await self.job_repo.load(scenario_id, job_id)
            if job is None or job.scenario_id != scenario_id:
                raise JobNotFoundError(details={"scenario_id": scenario_id, "job_id": job_id})
            if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
                raise JobAlreadyTerminalError(
                    details={"status": job.status.value},
                )

            now = utc_now_rfc3339()
            cleared: list[str] = []
            if job.type == JobType.WORLD:
                root = self.package_repo.package_dir(scenario_id) / "sections"
                if root.exists():
                    await remove_dir_tree(root)
                cleared = ["sections"]

            job = job.model_copy(
                update={
                    "status": JobStatus.CANCELED,
                    "finished_at": now,
                    "updated_at": now,
                    "current_step_label": "已取消",
                    "error_code": None,
                    "error_message": None,
                }
            )
            await self.job_repo.save(job)

            pkg.lifecycle_phase = LifecyclePhase.INTAKE_COMMITTED
            pkg.updated_at = now
            await self.package_repo.save(pkg)

        return CancelJobResponse(
            job_id=job_id,
            status=JobStatus.CANCELED,
            cleared_assets=cleared,
            lifecycle_phase_after=LifecyclePhase.INTAKE_COMMITTED.value,
            finished_at=now,
        )
