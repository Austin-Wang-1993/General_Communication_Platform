"""R2 本节复盘（API §6.1 / §6.2，PRD §6.8）。"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from app.clients.llm_client import LlmClient
from app.errors import (
    ChapterNotFoundError,
    LifecyclePhaseError,
    LlmFailureError,
    ScenarioNotFoundError,
    SectionNoTurnsYetError,
    SectionNotFoundError,
)
from app.lib.clock import utc_now_rfc3339
from app.models.analytics_api import SectionAnalyticsLatestResponse, SectionAnalyticsPostResponse
from app.models.enums import LifecyclePhase
from app.models.section_assets import SectionMissionPayload, SectionNarrativePayload
from app.models.story_assets import CharacterRosterFile, StoryFrameworkFile
from app.repositories.base import get_scenario_lock, read_json
from app.repositories.framework_repo import FrameworkRepo
from app.repositories.package_repo import PackageRepo
from app.repositories.roster_repo import RosterRepo
from app.repositories.section_analytics_repo import SectionAnalyticsRepo
from app.repositories.turns_repo import TurnsRepo

logger = logging.getLogger(__name__)

_RUNTIME_ANALYTICS = frozenset({LifecyclePhase.RUNTIME_ACTIVE})


class SectionAnalyticsService:
    def __init__(
        self,
        *,
        package_repo: PackageRepo,
        framework_repo: FrameworkRepo,
        roster_repo: RosterRepo,
        turns_repo: TurnsRepo,
        analytics_repo: SectionAnalyticsRepo,
        llm_client: LlmClient,
    ) -> None:
        self.package_repo = package_repo
        self.framework_repo = framework_repo
        self.roster_repo = roster_repo
        self.turns_repo = turns_repo
        self.analytics_repo = analytics_repo
        self.llm = llm_client

    def _locate_section(self, sf: StoryFrameworkFile, ch: int, sec: int) -> None:
        for chapter in sf.story_framework.chapters:
            if chapter.chapter_id != ch:
                continue
            for section in chapter.sections:
                if section.section_id == sec:
                    return
            raise SectionNotFoundError(details={"chapter_id": ch, "section_id": sec})
        raise ChapterNotFoundError(details={"chapter_id": ch})

    async def _load_narrative(self, scenario_id: str, ch: int, sec: int) -> SectionNarrativePayload:
        path = self.package_repo.package_dir(scenario_id) / "sections" / f"ch{ch}_sec{sec}" / "narrative.json"
        raw = await read_json(path)
        if not isinstance(raw, dict):
            raise SectionNotFoundError(
                details={"missing": "narrative.json", "chapter_id": ch, "section_id": sec},
            )
        try:
            return SectionNarrativePayload.model_validate(raw)
        except ValidationError as e:
            raise SectionNotFoundError(
                details={"chapter_id": ch, "section_id": sec, "reason": str(e)},
            ) from e

    async def _load_mission(self, scenario_id: str, ch: int, sec: int) -> SectionMissionPayload:
        path = self.package_repo.package_dir(scenario_id) / "sections" / f"ch{ch}_sec{sec}" / "mission.json"
        raw = await read_json(path)
        if not isinstance(raw, dict):
            raise SectionNotFoundError(
                details={"missing": "mission.json", "chapter_id": ch, "section_id": sec},
            )
        try:
            return SectionMissionPayload.model_validate(raw)
        except ValidationError as e:
            raise SectionNotFoundError(
                details={"chapter_id": ch, "section_id": sec, "reason": str(e)},
            ) from e

    async def _load_roster(self, scenario_id: str) -> CharacterRosterFile:
        raw = await self.roster_repo.load_raw(scenario_id)
        if not isinstance(raw, dict):
            raise LifecyclePhaseError(
                message="缺少角色表 roster.json",
                details={"scenario_id": scenario_id},
            )
        return CharacterRosterFile.model_validate(raw)

    def _normalize_analytics_dict(
        self,
        raw: dict[str, Any],
        *,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
        evaluated_through_turn_id: str,
    ) -> dict[str, Any]:
        d = dict(raw)
        if "section_analytics" in d and isinstance(d["section_analytics"], dict):
            d = dict(d["section_analytics"])
        d["scenario_id"] = scenario_id
        d["chapter_id"] = chapter_id
        d["section_id"] = section_id
        d["evaluated_through_turn_id"] = evaluated_through_turn_id
        d["generated_at"] = utc_now_rfc3339()
        return d

    async def post_section_analytics(
        self,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
    ) -> SectionAnalyticsPostResponse:
        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is None:
                raise ScenarioNotFoundError(details={"scenario_id": scenario_id})
            if pkg.lifecycle_phase not in _RUNTIME_ANALYTICS:
                raise LifecyclePhaseError(
                    message="仅运行态可生成本节复盘",
                    details={"lifecycle_phase": pkg.lifecycle_phase.value},
                )
            if pkg.current_chapter_id != chapter_id or pkg.current_section_id != section_id:
                raise LifecyclePhaseError(
                    message="本节复盘仅针对当前指针所在小节",
                    details={
                        "current_chapter_id": pkg.current_chapter_id,
                        "current_section_id": pkg.current_section_id,
                    },
                )

            fw_raw = await self.framework_repo.load_raw(scenario_id)
            if not isinstance(fw_raw, dict):
                raise LifecyclePhaseError(message="缺少 framework.json")
            sf = StoryFrameworkFile.model_validate(fw_raw)
            self._locate_section(sf, chapter_id, section_id)

            turns = await self.turns_repo.read_all(scenario_id, chapter_id, section_id)
            if not turns:
                raise SectionNoTurnsYetError()
            last_tid = str(turns[-1].get("turn_id", ""))
            if not last_tid:
                raise SectionNoTurnsYetError(details={"reason": "last_turn_missing_id"})

            narrative = await self._load_narrative(scenario_id, chapter_id, section_id)
            mission = await self._load_mission(scenario_id, chapter_id, section_id)
            roster = await self._load_roster(scenario_id)

            payload: dict[str, Any] = {
                "scenario_id": scenario_id,
                "chapter_id": chapter_id,
                "section_id": section_id,
                "section_narrative": narrative.model_dump(mode="json"),
                "section_mission": mission.model_dump(mode="json"),
                "character_roster": roster.character_roster.model_dump(mode="json"),
                "prior_turns": turns,
            }
            raw = await self.llm.generate_section_analytics_json(payload=payload)
            if not isinstance(raw, dict):
                raise LlmFailureError(message="本节复盘 LLM 输出非对象")
            d = self._normalize_analytics_dict(
                raw,
                scenario_id=scenario_id,
                chapter_id=chapter_id,
                section_id=section_id,
                evaluated_through_turn_id=last_tid,
            )
            try:
                out = SectionAnalyticsPostResponse.model_validate(d)
            except ValidationError as e:
                raw2 = await self.llm.generate_section_analytics_json(
                    payload=payload,
                    repair_hint=(
                        "Flat JSON: evaluated_through_turn_id must equal last prior_turns[].turn_id; "
                        "section_analytics_status ready; holistic_feedback_markdown 200-20000 chars Markdown, "
                        "mostly English with structured feedback."
                    ),
                    temperature=0.25,
                )
                if not isinstance(raw2, dict):
                    raise LlmFailureError(message="本节复盘修复重试仍失败") from e
                d2 = self._normalize_analytics_dict(
                    raw2,
                    scenario_id=scenario_id,
                    chapter_id=chapter_id,
                    section_id=section_id,
                    evaluated_through_turn_id=last_tid,
                )
                try:
                    out = SectionAnalyticsPostResponse.model_validate(d2)
                except ValidationError as e2:
                    raise LlmFailureError(
                        message="本节复盘 JSON 校验失败",
                        details={"errors": str(e2)[:800]},
                    ) from e2

            if out.section_analytics_status != "ready":
                raise LlmFailureError(message="本节复盘未返回 ready 状态")

            await self.analytics_repo.save(
                scenario_id,
                chapter_id,
                section_id,
                out.model_dump(mode="json"),
            )

        return out

    async def get_section_analytics_latest(
        self,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
    ) -> SectionAnalyticsLatestResponse | None:
        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is None:
                raise ScenarioNotFoundError(details={"scenario_id": scenario_id})
            if pkg.lifecycle_phase not in _RUNTIME_ANALYTICS:
                raise LifecyclePhaseError(
                    message="仅运行态可读取本节复盘",
                    details={"lifecycle_phase": pkg.lifecycle_phase.value},
                )
            fw_raw = await self.framework_repo.load_raw(scenario_id)
            if not isinstance(fw_raw, dict):
                raise LifecyclePhaseError(message="缺少 framework.json")
            sf = StoryFrameworkFile.model_validate(fw_raw)
            self._locate_section(sf, chapter_id, section_id)

            raw = await self.analytics_repo.load(scenario_id, chapter_id, section_id)
            if raw is None:
                return None
            if raw.get("section_analytics_status") != "ready":
                return None
            try:
                et = str(raw.get("evaluated_through_turn_id", ""))
                md = str(raw.get("holistic_feedback_markdown", ""))
                gen = str(raw.get("generated_at", ""))
                return SectionAnalyticsLatestResponse(
                    linked_turn_id=et,
                    section_analytics_status="ready",
                    holistic_feedback_markdown=md,
                    generated_at=gen,
                )
            except ValidationError:
                logger.warning("analytics.json invalid for %s ch%s sec%s", scenario_id, chapter_id, section_id)
                return None
