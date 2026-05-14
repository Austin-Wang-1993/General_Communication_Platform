"""Framework + roster 创作 Job（API 文档 §3.1 + 业务流程 §2.2）。"""

from __future__ import annotations

import logging
from typing import Any

from app.clients.llm_client import LlmClient
from app.errors import (
    ActiveJobConflictError,
    GcpError,
    LifecyclePhaseError,
    LlmFailureError,
    ScenarioNotFoundError,
)
from app.lib.clock import utc_now_rfc3339
from app.lib.ids import new_job_id
from app.models.creation_jobs import JobRecord, JobStatus, JobType, StartFrameworkJobResponse
from app.models.enums import LifecyclePhase
from app.models.story_assets import CharacterRosterFile, StoryFrameworkFile
from app.repositories.analysis_repo import AnalysisRepo
from app.repositories.base import get_scenario_lock
from app.repositories.framework_repo import FrameworkRepo
from app.repositories.intake_repo import IntakeRepo
from app.repositories.job_repo import JobRepo
from app.repositories.package_repo import PackageRepo
from app.repositories.roster_repo import RosterRepo

logger = logging.getLogger(__name__)

_ALLOWED_START = frozenset({LifecyclePhase.INTAKE_COMMITTED, LifecyclePhase.CREATION_FAILED})

STEP_LABEL_FW = "正在生成剧情框架…"
STEP_LABEL_ROSTER = "正在生成参与角色…"


class FrameworkJobService:
    def __init__(
        self,
        *,
        package_repo: PackageRepo,
        job_repo: JobRepo,
        framework_repo: FrameworkRepo,
        roster_repo: RosterRepo,
        intake_repo: IntakeRepo,
        analysis_repo: AnalysisRepo,
        llm_client: LlmClient,
    ) -> None:
        self.package_repo = package_repo
        self.job_repo = job_repo
        self.framework_repo = framework_repo
        self.roster_repo = roster_repo
        self.intake_repo = intake_repo
        self.analysis_repo = analysis_repo
        self.llm = llm_client

    async def start_framework_job(self, scenario_id: str) -> StartFrameworkJobResponse:
        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is None:
                raise ScenarioNotFoundError(details={"scenario_id": scenario_id})
            if pkg.lifecycle_phase not in _ALLOWED_START:
                raise LifecyclePhaseError(
                    message="当前生命周期不允许启动 framework job",
                    details={
                        "lifecycle_phase": pkg.lifecycle_phase.value,
                        "allowed": sorted(p.value for p in _ALLOWED_START),
                    },
                )
            if not await self.package_repo.asset_exists(
                scenario_id, "intake.json"
            ) or not await self.package_repo.asset_exists(scenario_id, "analysis.json"):
                raise LifecyclePhaseError(
                    message="缺少五字段或扩写产物，请先完成 commit-intake",
                    details={"need": ["intake.json", "analysis.json"]},
                )
            if await self.job_repo.has_active_job(scenario_id):
                raise ActiveJobConflictError()

            job_id = new_job_id()
            now = utc_now_rfc3339()
            record = JobRecord(
                job_id=job_id,
                type=JobType.FRAMEWORK,
                scenario_id=scenario_id,
                status=JobStatus.RUNNING,
                current_step_label=STEP_LABEL_FW,
                progress_hint=None,
                created_at=now,
                updated_at=now,
                finished_at=None,
                error_code=None,
                error_message=None,
            )
            await self.job_repo.save(record)

            pkg.lifecycle_phase = LifecyclePhase.CREATION_RUNNING
            pkg.updated_at = now
            await self.package_repo.save(pkg)

        return StartFrameworkJobResponse(
            job_id=job_id,
            type=JobType.FRAMEWORK,
            scenario_id=scenario_id,
            status=JobStatus.RUNNING,
            current_step_label=STEP_LABEL_FW,
            created_at=now,
        )

    async def run_framework_pipeline(self, scenario_id: str, job_id: str) -> None:
        try:
            await self._execute_framework_job(scenario_id, job_id)
        except GcpError as e:
            logger.warning("framework job %s failed: %s", job_id, e.to_payload())
            await self._finalize_failure(scenario_id, job_id, e.error_code, e.message)
        except Exception as e:
            logger.exception("framework job %s crashed", job_id)
            await self._finalize_failure(
                scenario_id,
                job_id,
                "internal_error",
                str(e)[:2000],
            )

    async def _finalize_failure(
        self,
        scenario_id: str,
        job_id: str,
        error_code: str,
        error_message: str,
    ) -> None:
        now = utc_now_rfc3339()
        j = await self.job_repo.load(scenario_id, job_id)
        if j:
            if j.status == JobStatus.CANCELED:
                return
            j = j.model_copy(
                update={
                    "status": JobStatus.FAILED,
                    "finished_at": now,
                    "updated_at": now,
                    "error_code": error_code,
                    "error_message": error_message[:4000],
                    "current_step_label": "失败",
                }
            )
            await self.job_repo.save(j)
        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is not None:
                pkg.lifecycle_phase = LifecyclePhase.CREATION_FAILED
                pkg.updated_at = now
                await self.package_repo.save(pkg)

    async def _touch_job_label(self, scenario_id: str, job_id: str, label: str) -> None:
        j = await self.job_repo.load(scenario_id, job_id)
        if j is None:
            return
        j = j.model_copy(update={"current_step_label": label, "updated_at": utc_now_rfc3339()})
        await self.job_repo.save(j)

    async def _job_still_running(self, scenario_id: str, job_id: str) -> bool:
        j = await self.job_repo.load(scenario_id, job_id)
        return j is not None and j.status == JobStatus.RUNNING

    async def _execute_framework_job(self, scenario_id: str, job_id: str) -> None:
        intake = await self.intake_repo.load(scenario_id)
        analysis = await self.analysis_repo.load(scenario_id)
        if not intake or not analysis:
            raise LifecyclePhaseError(message="intake 或 analysis 缺失")

        bundle: dict[str, Any] = {
            "scenario_id": scenario_id,
            "user_display_name": str(intake.get("user_display_name", "")),
            "enriched_scene_description": str(analysis.get("enriched_scene_description", "")),
            "enriched_user_goal": str(analysis.get("enriched_user_goal", "")),
            "normalized_vocabulary": analysis.get("normalized_vocabulary", []),
        }
        if not isinstance(bundle["normalized_vocabulary"], list):
            bundle["normalized_vocabulary"] = []

        raw = await self.llm.generate_story_framework_json(payload=bundle)
        fw = self._validate_framework(raw, scenario_id)
        if fw is None:
            raw2 = await self.llm.generate_story_framework_json(
                payload=bundle,
                repair_hint=(
                    "Return ONLY JSON with key story_framework. "
                    "chapter_id book-wide unique strictly increasing from 1; "
                    "section_id unique per chapter strictly increasing from 1; "
                    "1<=K<=20 total sections."
                ),
                temperature=0.35,
            )
            fw = self._validate_framework(raw2, scenario_id)
        if fw is None:
            raise LlmFailureError(message="剧情框架 JSON 校验失败")

        await self.framework_repo.save(scenario_id, fw.model_dump(mode="json"))

        if not await self._job_still_running(scenario_id, job_id):
            return

        await self._touch_job_label(scenario_id, job_id, STEP_LABEL_ROSTER)

        roster_bundle = dict(bundle)
        roster_bundle["story_framework"] = fw.story_framework.model_dump(mode="json")

        raw_r = await self.llm.generate_character_roster_json(payload=roster_bundle)
        roster = self._validate_roster(raw_r, scenario_id)
        if roster is None:
            raw_r2 = await self.llm.generate_character_roster_json(
                payload=roster_bundle,
                repair_hint=(
                    "Return ONLY JSON with key character_roster. "
                    "Exactly one character with is_user true and character_id 'user'; "
                    "2-6 characters total; unique npc character_id."
                ),
                temperature=0.35,
            )
            roster = self._validate_roster(raw_r2, scenario_id)
        if roster is None:
            raise LlmFailureError(message="角色表 JSON 校验失败")

        await self.roster_repo.save(scenario_id, roster.model_dump(mode="json"))

        now = utc_now_rfc3339()
        j = await self.job_repo.load(scenario_id, job_id)
        if j is None or j.status != JobStatus.RUNNING:
            return
        j = j.model_copy(
            update={
                "status": JobStatus.SUCCEEDED,
                "finished_at": now,
                "updated_at": now,
                "current_step_label": "完成",
                "error_code": None,
                "error_message": None,
            }
        )
        await self.job_repo.save(j)

        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is not None:
                pkg.lifecycle_phase = LifecyclePhase.INTAKE_COMMITTED
                pkg.updated_at = now
                await self.package_repo.save(pkg)

    def _validate_framework(self, raw: object, scenario_id: str) -> StoryFrameworkFile | None:
        if not isinstance(raw, dict):
            return None
        try:
            f = StoryFrameworkFile.model_validate(raw)
        except Exception:
            return None
        if f.story_framework.scenario_id != scenario_id:
            return None
        return f

    def _validate_roster(self, raw: object, scenario_id: str) -> CharacterRosterFile | None:
        if not isinstance(raw, dict):
            return None
        try:
            r = CharacterRosterFile.model_validate(raw)
        except Exception:
            return None
        if r.character_roster.scenario_id != scenario_id:
            return None
        return r
