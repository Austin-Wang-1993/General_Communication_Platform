"""五字段提交与扩写（API 文档 §2.5 + PRD §6.1）。"""

from __future__ import annotations

import asyncio

from pydantic import ValidationError

from app.clients.llm_client import LlmClient
from app.errors import (
    FrameworkAlreadyExistsError,
    IntakeUnrelatedTopicError,
    LifecyclePhaseError,
    LlmFailureError,
    ScenarioNotFoundError,
)
from app.lib.clock import utc_now_rfc3339
from app.models.enums import LifecyclePhase
from app.models.intake import (
    CommitIntakeRequest,
    CommitIntakeResponse,
    IntakeSnapshot,
    ScenarioAnalysis,
)
from app.repositories.analysis_repo import AnalysisRepo
from app.repositories.base import get_scenario_lock, remove_dir_tree
from app.repositories.intake_repo import IntakeRepo
from app.repositories.package_repo import PackageRepo
from app.validators.intake_fields import (
    topics_loosely_related,
    trim_and_check_display_name,
    trim_scenario_title,
    validate_scene_brief,
    validate_user_goal_brief,
    validate_vocabulary_list,
)

_ALLOWED_PHASES_COMMIT = frozenset(
    {
        LifecyclePhase.DRAFT,
        LifecyclePhase.INTAKE_COMMITTED,
        LifecyclePhase.CREATION_FAILED,
        LifecyclePhase.CREATION_SUCCEEDED,
    }
)


class IntakeService:
    def __init__(
        self,
        *,
        package_repo: PackageRepo,
        intake_repo: IntakeRepo,
        analysis_repo: AnalysisRepo,
        llm_client: LlmClient,
    ) -> None:
        self.package_repo = package_repo
        self.intake_repo = intake_repo
        self.analysis_repo = analysis_repo
        self.llm = llm_client

    async def commit_intake(
        self,
        scenario_id: str,
        body: CommitIntakeRequest,
    ) -> CommitIntakeResponse:
        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is None:
                raise ScenarioNotFoundError(details={"scenario_id": scenario_id})

            if pkg.lifecycle_phase not in _ALLOWED_PHASES_COMMIT:
                raise LifecyclePhaseError(
                    message="当前生命周期阶段不允许提交五字段",
                    details={
                        "lifecycle_phase": pkg.lifecycle_phase.value,
                        "allowed": sorted(p.value for p in _ALLOWED_PHASES_COMMIT),
                    },
                )

            has_fw = await self.package_repo.asset_exists(scenario_id, "framework.json")
            if has_fw and not body.force_reset_creation:
                raise FrameworkAlreadyExistsError()

            reset_applied = False
            if body.force_reset_creation:
                reset_applied = await self._g3_reset_creation(scenario_id)

            title = trim_scenario_title(body.scenario_title)
            display = trim_and_check_display_name(body.user_display_name)
            scene = validate_scene_brief(body.scene_brief)
            goal = validate_user_goal_brief(body.user_goal_brief)
            vocab = validate_vocabulary_list(body.vocabulary_list)

            if not topics_loosely_related(scene, goal):
                raise IntakeUnrelatedTopicError()

            snapshot_dict = {
                "scenario_title": title,
                "user_display_name": display,
                "scene_brief": scene,
                "user_goal_brief": goal,
                "vocabulary_list": vocab,
            }
            snapshot = IntakeSnapshot.model_validate(snapshot_dict)

            raw = await self.llm.expand_intake(snapshot=snapshot_dict)
            analysis = self._parse_and_validate_analysis(raw)
            if analysis is None:
                raw2 = await self.llm.expand_intake(
                    snapshot=snapshot_dict,
                    repair_hint=(
                        "Your previous JSON failed validation. Return ONLY a JSON object with keys "
                        "enriched_scene_description (English, >=200 chars), "
                        "enriched_user_goal (English, >=80 chars), "
                        "normalized_vocabulary (array of up to 200 English tokens, lowercase except proper nouns). "
                        "All three keys are required."
                    ),
                    temperature=0.35,
                )
                analysis = self._parse_and_validate_analysis(raw2)
            if analysis is None:
                raise LlmFailureError(
                    message="扩写结果不符合长度与格式要求",
                    details={"hint": "请稍后重试或调整输入"},
                )

            now = utc_now_rfc3339()
            intake_doc = {
                **snapshot_dict,
                "scenario_id": scenario_id,
                "committed_at": now,
            }
            await self.intake_repo.save(scenario_id, intake_doc)

            analysis_doc = {
                "scenario_id": scenario_id,
                "enriched_scene_description": analysis.enriched_scene_description,
                "enriched_user_goal": analysis.enriched_user_goal,
                "normalized_vocabulary": analysis.normalized_vocabulary,
            }
            await self.analysis_repo.save(scenario_id, analysis_doc)

            pkg.scenario_title = title
            pkg.lifecycle_phase = LifecyclePhase.INTAKE_COMMITTED
            pkg.updated_at = now
            await self.package_repo.save(pkg)

            return CommitIntakeResponse(
                scenario_id=scenario_id,
                lifecycle_phase=LifecyclePhase.INTAKE_COMMITTED.value,
                intake_snapshot=snapshot,
                scenario_analysis=analysis,
                reset_applied=reset_applied,
                updated_at=now,
            )

    def _parse_and_validate_analysis(self, raw: object) -> ScenarioAnalysis | None:
        if not isinstance(raw, dict):
            return None
        try:
            vocab = self._normalize_vocabulary_field(raw.get("normalized_vocabulary"))
            return ScenarioAnalysis.model_validate(
                {
                    "enriched_scene_description": raw["enriched_scene_description"],
                    "enriched_user_goal": raw["enriched_user_goal"],
                    "normalized_vocabulary": vocab,
                }
            )
        except (KeyError, TypeError, ValidationError):
            return None

    def _normalize_vocabulary_field(self, raw_vocab: object) -> list[str]:
        if isinstance(raw_vocab, str):
            parts = raw_vocab.replace(",", "\n").splitlines()
            words = [w.strip() for w in parts if w.strip()]
        elif isinstance(raw_vocab, list):
            words = [str(x).strip() for x in raw_vocab if str(x).strip()]
        else:
            words = []
        seen: set[str] = set()
        out: list[str] = []
        for w in words:
            key = w.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(w)
            if len(out) >= 200:
                break
        return out

    async def _g3_reset_creation(self, scenario_id: str) -> bool:
        """删除 framework / roster / sections / jobs。若曾存在任一项则返回 True。"""
        root = self.package_repo.package_dir(scenario_id)
        touched = False

        def _unlink_known_files() -> bool:
            flag = False
            for name in ("framework.json", "roster.json"):
                p = root / name
                if p.exists():
                    p.unlink()
                    flag = True
            return flag

        if await asyncio.to_thread(_unlink_known_files):
            touched = True

        if (root / "sections").exists():
            touched = True
            await remove_dir_tree(root / "sections")
        if (root / "jobs").exists():
            touched = True
            await remove_dir_tree(root / "jobs")

        return touched
