"""World Job：全书小节 §6.4 + §6.5（API §3.2 + 业务流程 §2.2）。"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.clients.llm_client import LlmClient
from app.errors import (
    ActiveJobConflictError,
    GcpError,
    LifecyclePhaseError,
    LlmFailureError,
    ScenarioNotFoundError,
    SectionsAlreadyExistError,
)
from app.lib.clock import utc_now_rfc3339
from app.lib.ids import new_job_id
from app.models.creation_jobs import (
    JobRecord,
    JobStatus,
    JobType,
    StartWorldJobRequest,
    StartWorldJobResponse,
)
from app.models.enums import LifecyclePhase
from app.models.section_assets import SectionMissionPayload, SectionNarrativePayload
from app.models.story_assets import (
    CharacterRosterFile,
    FrameworkChapter,
    FrameworkSection,
    StoryFrameworkFile,
)
from app.repositories.analysis_repo import AnalysisRepo
from app.repositories.base import get_scenario_lock, remove_dir_tree, write_json_atomic
from app.repositories.framework_repo import FrameworkRepo
from app.repositories.job_repo import JobRepo
from app.repositories.package_repo import PackageRepo
from app.repositories.roster_repo import RosterRepo

logger = logging.getLogger(__name__)

_NARRATIVE_KEYS = frozenset(
    {"scenario_id", "chapter_id", "section_id", "section_body", "appearing_npc_ids"}
)
_MISSION_KEYS = frozenset({"scenario_id", "chapter_id", "section_id", "section_objective"})

_ALLOWED_WORLD = frozenset(
    {
        LifecyclePhase.INTAKE_COMMITTED,
        LifecyclePhase.CREATION_FAILED,
        LifecyclePhase.CREATION_SUCCEEDED,
    }
)


def _ordered_chapter_sections(sf: StoryFrameworkFile) -> list[tuple[FrameworkChapter, FrameworkSection]]:
    pairs: list[tuple[FrameworkChapter, FrameworkSection]] = []
    for ch in sf.story_framework.chapters:
        for sec in ch.sections:
            pairs.append((ch, sec))
    return pairs


def _framework_section_slice(ch: FrameworkChapter, sec: FrameworkSection) -> dict[str, Any]:
    return {
        "chapter_id": ch.chapter_id,
        "chapter_title": ch.chapter_title,
        "chapter_summary": ch.chapter_summary,
        "section_id": sec.section_id,
        "section_title": sec.section_title,
        "section_summary": sec.section_summary,
    }


class WorldJobService:
    def __init__(
        self,
        *,
        package_repo: PackageRepo,
        job_repo: JobRepo,
        framework_repo: FrameworkRepo,
        roster_repo: RosterRepo,
        analysis_repo: AnalysisRepo,
        llm_client: LlmClient,
    ) -> None:
        self.package_repo = package_repo
        self.job_repo = job_repo
        self.framework_repo = framework_repo
        self.roster_repo = roster_repo
        self.analysis_repo = analysis_repo
        self.llm = llm_client

    async def start_world_job(
        self,
        scenario_id: str,
        body: StartWorldJobRequest,
    ) -> StartWorldJobResponse:
        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is None:
                raise ScenarioNotFoundError(details={"scenario_id": scenario_id})
            if pkg.lifecycle_phase not in _ALLOWED_WORLD:
                raise LifecyclePhaseError(
                    message="当前生命周期不允许启动 world job",
                    details={
                        "lifecycle_phase": pkg.lifecycle_phase.value,
                        "allowed": sorted(p.value for p in _ALLOWED_WORLD),
                    },
                )
            if not await self.package_repo.asset_exists(
                scenario_id, "framework.json"
            ) or not await self.package_repo.asset_exists(scenario_id, "roster.json"):
                raise LifecyclePhaseError(
                    message="缺少 framework.json 或 roster.json，请先完成 framework Job",
                    details={"need": ["framework.json", "roster.json"]},
                )
            if await self.job_repo.has_active_job(scenario_id):
                raise ActiveJobConflictError()

            need_force = (
                pkg.lifecycle_phase == LifecyclePhase.CREATION_SUCCEEDED
                or await self._any_section_json(scenario_id)
            )
            if need_force and not body.force_regenerate:
                raise SectionsAlreadyExistError()
            if body.force_regenerate:
                sec_root = self.package_repo.package_dir(scenario_id) / "sections"
                if sec_root.exists():
                    await remove_dir_tree(sec_root)

            fw_raw = await self.framework_repo.load_raw(scenario_id)
            sf = StoryFrameworkFile.model_validate(fw_raw) if fw_raw else None
            if sf is None:
                raise LifecyclePhaseError(message="framework.json 无效或缺失")
            pairs = _ordered_chapter_sections(sf)
            total = len(pairs)
            if total < 1:
                raise LifecyclePhaseError(message="framework 中无小节")

            job_id = new_job_id()
            now = utc_now_rfc3339()
            first_ch, first_sec = pairs[0]
            label0 = f"正在生成第 {first_ch.chapter_id} 章第 {first_sec.section_id} 节场景…"
            record = JobRecord(
                job_id=job_id,
                type=JobType.WORLD,
                scenario_id=scenario_id,
                status=JobStatus.RUNNING,
                current_step_label=label0,
                progress_hint=f"1/{total}",
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

        return StartWorldJobResponse(
            job_id=job_id,
            type=JobType.WORLD,
            scenario_id=scenario_id,
            status=JobStatus.RUNNING,
            current_step_label=label0,
            progress_hint=f"1/{total}",
            created_at=now,
        )

    async def run_world_pipeline(self, scenario_id: str, job_id: str) -> None:
        try:
            await self._execute_world_job(scenario_id, job_id)
        except GcpError as e:
            logger.warning("world job %s failed: %s", job_id, e.to_payload())
            await self._finalize_failure(scenario_id, job_id, e.error_code, e.message)
        except Exception as e:
            logger.exception("world job %s crashed", job_id)
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

    async def _any_section_json(self, scenario_id: str) -> bool:
        root = self.package_repo.package_dir(scenario_id) / "sections"

        def scan() -> bool:
            if not root.exists():
                return False
            for p in root.rglob("*.json"):
                return True
            return False

        return await asyncio.to_thread(scan)

    async def _patch_job(
        self,
        scenario_id: str,
        job_id: str,
        *,
        label: str,
        progress_hint: str,
    ) -> None:
        j = await self.job_repo.load(scenario_id, job_id)
        if j is None or j.status != JobStatus.RUNNING:
            return
        j = j.model_copy(
            update={
                "current_step_label": label,
                "progress_hint": progress_hint,
                "updated_at": utc_now_rfc3339(),
            }
        )
        await self.job_repo.save(j)

    async def _execute_world_job(self, scenario_id: str, job_id: str) -> None:
        fw_raw = await self.framework_repo.load_raw(scenario_id)
        roster_raw = await self.roster_repo.load_raw(scenario_id)
        analysis = await self.analysis_repo.load(scenario_id)
        if not fw_raw or not roster_raw or not analysis:
            raise LifecyclePhaseError(message="framework、roster 或 analysis 缺失")

        sf = StoryFrameworkFile.model_validate(fw_raw)
        roster = CharacterRosterFile.model_validate(roster_raw)
        pairs = _ordered_chapter_sections(sf)
        total = len(pairs)
        roster_dump = roster.character_roster.model_dump(mode="json")
        enriched_scene = str(analysis.get("enriched_scene_description", ""))
        enriched_goal = str(analysis.get("enriched_user_goal", ""))
        vocab = analysis.get("normalized_vocabulary", [])
        if not isinstance(vocab, list):
            vocab = []
        allowed_npc_list = sorted(
            c.character_id for c in roster.character_roster.characters if not c.is_user
        )
        allowed_npc_set = set(allowed_npc_list)
        npc_hint = ", ".join(allowed_npc_list)

        for idx, (ch, sec) in enumerate(pairs, start=1):
            j = await self.job_repo.load(scenario_id, job_id)
            if j is None or j.status != JobStatus.RUNNING:
                return

            label_n = f"正在生成第 {ch.chapter_id} 章第 {sec.section_id} 节场景…"
            await self._patch_job(scenario_id, job_id, label=label_n, progress_hint=f"{idx}/{total}")

            fw_slice = _framework_section_slice(ch, sec)
            narrative_payload: dict[str, Any] = {
                "scenario_id": scenario_id,
                "chapter_id": ch.chapter_id,
                "section_id": sec.section_id,
                "framework_section": fw_slice,
                "character_roster": roster_dump,
                "enriched_scene_description": enriched_scene,
                "enriched_user_goal": enriched_goal,
                "normalized_vocabulary": vocab,
            }
            raw_n = await self.llm.generate_section_narrative_json(payload=narrative_payload)
            nar, why = self._validate_narrative(
                raw_n,
                scenario_id,
                ch.chapter_id,
                sec.section_id,
                allowed_npc_ids=allowed_npc_set,
            )
            if nar is None:
                logger.warning(
                    "world narrative first pass invalid ch=%s sec=%s why=%s raw=%s",
                    ch.chapter_id,
                    sec.section_id,
                    why,
                    str(raw_n)[:800],
                )
                raw_n2 = await self.llm.generate_section_narrative_json(
                    payload=narrative_payload,
                    repair_hint=(
                        "Return a single FLAT JSON object (no markdown). Keys exactly: "
                        "scenario_id, chapter_id, section_id, section_body, appearing_npc_ids. "
                        "section_body: English, >=300 chars. "
                        "appearing_npc_ids: length 1 or 2; use ONLY these roster NPC ids: "
                        f"{npc_hint}. Never include user."
                    ),
                    temperature=0.35,
                )
                nar, why = self._validate_narrative(
                    raw_n2,
                    scenario_id,
                    ch.chapter_id,
                    sec.section_id,
                    allowed_npc_ids=allowed_npc_set,
                )
            if nar is None:
                raw_n3 = await self.llm.generate_section_narrative_json(
                    payload=narrative_payload,
                    repair_hint=(
                        "Previous JSON failed schema. Output ONLY one JSON object. "
                        f"Copy scenario_id exactly from input. chapter_id must be {ch.chapter_id}, "
                        f"section_id must be {sec.section_id}. "
                        f"appearing_npc_ids MUST use 1-2 ids from this list only: {npc_hint}. "
                        "section_body: English narrative >=300 characters for THIS section's framework_section."
                    ),
                    temperature=0.2,
                )
                nar, why = self._validate_narrative(
                    raw_n3,
                    scenario_id,
                    ch.chapter_id,
                    sec.section_id,
                    allowed_npc_ids=allowed_npc_set,
                )
            if nar is None:
                hint = why or "unknown"
                raise LlmFailureError(
                    message=(
                        f"小节 ({ch.chapter_id},{sec.section_id}) narrative 校验失败；原因：{hint}"
                    )[:4000],
                    details={
                        "validation_hint": why,
                        "allowed_npc_ids": allowed_npc_list,
                    },
                )

            base = self._section_dir(scenario_id, ch.chapter_id, sec.section_id)
            await write_json_atomic(base / "narrative.json", nar.model_dump(mode="json"))

            j = await self.job_repo.load(scenario_id, job_id)
            if j is None or j.status != JobStatus.RUNNING:
                return

            label_m = f"正在生成第 {ch.chapter_id} 章第 {sec.section_id} 节任务…"
            await self._patch_job(scenario_id, job_id, label=label_m, progress_hint=f"{idx}/{total}")

            mission_payload: dict[str, Any] = {
                "scenario_id": scenario_id,
                "chapter_id": ch.chapter_id,
                "section_id": sec.section_id,
                "framework_section": fw_slice,
                "section_narrative": nar.model_dump(mode="json"),
                "character_roster": roster_dump,
                "enriched_user_goal": enriched_goal,
            }
            raw_m = await self.llm.generate_section_mission_json(payload=mission_payload)
            miss, m_why = self._validate_mission(raw_m, scenario_id, ch.chapter_id, sec.section_id)
            if miss is None:
                raw_m2 = await self.llm.generate_section_mission_json(
                    payload=mission_payload,
                    repair_hint=(
                        "Single FLAT JSON object only. Keys exactly: scenario_id, chapter_id, section_id, "
                        "section_objective. section_objective: English 40-1200 chars aligned to section_narrative."
                    ),
                    temperature=0.35,
                )
                miss, m_why = self._validate_mission(raw_m2, scenario_id, ch.chapter_id, sec.section_id)
            if miss is None:
                raw_m3 = await self.llm.generate_section_mission_json(
                    payload=mission_payload,
                    repair_hint=(
                        "Schema failed. Output ONLY one JSON object. "
                        f"scenario_id from input; chapter_id={ch.chapter_id}; section_id={sec.section_id}. "
                        "section_objective: English 40-1200 chars, one clear learner task matching the narrative."
                    ),
                    temperature=0.2,
                )
                miss, m_why = self._validate_mission(raw_m3, scenario_id, ch.chapter_id, sec.section_id)
            if miss is None:
                mh = m_why or "unknown"
                raise LlmFailureError(
                    message=(
                        f"小节 ({ch.chapter_id},{sec.section_id}) mission 校验失败；原因：{mh}"
                    )[:4000],
                    details={"validation_hint": m_why},
                )

            await write_json_atomic(base / "mission.json", miss.model_dump(mode="json"))

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
                "progress_hint": f"{total}/{total}",
                "error_code": None,
                "error_message": None,
            }
        )
        await self.job_repo.save(j)

        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is not None:
                pkg.lifecycle_phase = LifecyclePhase.CREATION_SUCCEEDED
                pkg.updated_at = now
                await self.package_repo.save(pkg)

    def _section_dir(self, scenario_id: str, chapter_id: int, section_id: int) -> Path:
        return (
            self.package_repo.package_dir(scenario_id)
            / "sections"
            / f"ch{chapter_id}_sec{section_id}"
        )

    @staticmethod
    def _sanitize_appearing_npc_ids(raw: Any, allowed: set[str]) -> list[str] | None:
        """PRD：每节 1~2 名 NPC。模型若列出更多，只保留前两个合法且不重复的 id。"""
        if not isinstance(raw, list):
            return None
        out: list[str] = []
        seen: set[str] = set()
        for x in raw:
            tid = str(x).strip()
            if not tid or tid == "user" or tid not in allowed:
                continue
            if tid in seen:
                continue
            seen.add(tid)
            out.append(tid)
            if len(out) >= 2:
                break
        if not out:
            return None
        return out

    @staticmethod
    def _strip_extra_keys(d: dict[str, Any], keep: frozenset[str]) -> dict[str, Any]:
        return {k: v for k, v in d.items() if k in keep}

    @staticmethod
    def _unwrap_inner_dict(raw: object, inner_keys: tuple[str, ...]) -> dict[str, Any] | None:
        """接受根级扁平 JSON，或误包在 `section_narrative` / `narrative` 等键下的对象。"""
        if not isinstance(raw, dict):
            return None
        for k in inner_keys:
            inner = raw.get(k)
            if isinstance(inner, dict):
                return dict(inner)
        if len(raw) == 1:
            lone = next(iter(raw.values()))
            if isinstance(lone, dict):
                return dict(lone)
        return dict(raw)

    def _validate_narrative(
        self,
        raw: object,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
        *,
        allowed_npc_ids: set[str],
    ) -> tuple[SectionNarrativePayload | None, str | None]:
        d = self._unwrap_inner_dict(raw, ("section_narrative", "narrative"))
        if d is None:
            return None, "响应不是 JSON 对象"
        d = dict(d)
        # 以流水线上下文为准强制回显 id（减少模型抄错 chapter/section 导致整 Job 失败）
        d["scenario_id"] = scenario_id
        d["chapter_id"] = chapter_id
        d["section_id"] = section_id
        d = WorldJobService._strip_extra_keys(d, _NARRATIVE_KEYS)
        cleaned = WorldJobService._sanitize_appearing_npc_ids(d.get("appearing_npc_ids"), allowed_npc_ids)
        if cleaned is None:
            return None, "appearing_npc_ids 为空或无法解析（需至少 1 个 roster 中的 NPC id）"
        d["appearing_npc_ids"] = cleaned
        try:
            n = SectionNarrativePayload.model_validate(d)
        except ValidationError as e:
            return None, self._format_validation_errors(e)
        return n, None

    def _validate_mission(
        self,
        raw: object,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
    ) -> tuple[SectionMissionPayload | None, str | None]:
        d = self._unwrap_inner_dict(raw, ("section_mission", "mission"))
        if d is None:
            return None, "响应不是 JSON 对象"
        d = dict(d)
        d["scenario_id"] = scenario_id
        d["chapter_id"] = chapter_id
        d["section_id"] = section_id
        d = WorldJobService._strip_extra_keys(d, _MISSION_KEYS)
        try:
            m = SectionMissionPayload.model_validate(d)
        except ValidationError as e:
            return None, self._format_validation_errors(e)
        return m, None

    @staticmethod
    def _format_validation_errors(e: ValidationError) -> str:
        parts: list[str] = []
        for err in e.errors()[:10]:
            loc = ".".join(str(x) for x in err.get("loc", ()))
            msg = str(err.get("msg", ""))
            parts.append(f"{loc}: {msg}")
        return "; ".join(parts)[:2000]
