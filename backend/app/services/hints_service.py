"""R1 回答提示（API §5.1 / §5.2，PRD §6.7）。"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from app.clients.llm_client import LlmClient
from app.errors import (
    ChapterNotFoundError,
    LifecyclePhaseError,
    LlmFailureError,
    RuntimeNotAwaitingUserError,
    ScenarioNotFoundError,
    SectionNotFoundError,
    TurnNotFoundError,
)
from app.lib.clock import utc_now_rfc3339
from app.models.enums import LifecyclePhase
from app.models.hint_api import HintResponse, PostHintRequest
from app.models.section_assets import SectionMissionPayload, SectionNarrativePayload
from app.models.story_assets import CharacterRosterFile, StoryFrameworkFile
from app.repositories.base import get_scenario_lock, read_json
from app.repositories.framework_repo import FrameworkRepo
from app.repositories.hints_repo import HintsRepo
from app.repositories.package_repo import PackageRepo
from app.repositories.roster_repo import RosterRepo
from app.repositories.turns_repo import TurnsRepo
from app.validators.turn_rules import turn_expects_user_reply_active

logger = logging.getLogger(__name__)

_RUNTIME_HINTS = frozenset({LifecyclePhase.RUNTIME_ACTIVE})


class HintsService:
    def __init__(
        self,
        *,
        package_repo: PackageRepo,
        framework_repo: FrameworkRepo,
        roster_repo: RosterRepo,
        turns_repo: TurnsRepo,
        hints_repo: HintsRepo,
        llm_client: LlmClient,
    ) -> None:
        self.package_repo = package_repo
        self.framework_repo = framework_repo
        self.roster_repo = roster_repo
        self.turns_repo = turns_repo
        self.hints_repo = hints_repo
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

    @staticmethod
    def _last_npc_expecting_user(turns: list[dict[str, Any]]) -> dict[str, Any] | None:
        for t in reversed(turns):
            if turn_expects_user_reply_active(t) and t.get("speaker_id") != "user":
                return t
        return None

    @staticmethod
    def _assert_target_turn(turns: list[dict[str, Any]], target_turn_id: str) -> None:
        last = HintsService._last_npc_expecting_user(turns)
        if last is None:
            raise TurnNotFoundError(
                details={"target_turn_id": target_turn_id, "reason": "no_npc_expecting_user"},
            )
        if str(last.get("turn_id")) != str(target_turn_id):
            raise TurnNotFoundError(
                details={
                    "target_turn_id": target_turn_id,
                    "expected_turn_id": last.get("turn_id"),
                },
            )

    def _normalize_hint_dict(
        self,
        raw: dict[str, Any],
        *,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
        linked_turn_id: str,
    ) -> dict[str, Any]:
        d = dict(raw)
        if "hint" in d and isinstance(d["hint"], dict):
            d = dict(d["hint"])
        d["scenario_id"] = scenario_id
        d["chapter_id"] = chapter_id
        d["section_id"] = section_id
        d["linked_turn_id"] = linked_turn_id
        d["hint_status"] = "ready"
        d["generated_at"] = utc_now_rfc3339()
        return d

    async def post_hint(
        self,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
        body: PostHintRequest,
    ) -> HintResponse:
        target_turn_id = body.target_turn_id.strip()
        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is None:
                raise ScenarioNotFoundError(details={"scenario_id": scenario_id})
            if pkg.lifecycle_phase not in _RUNTIME_HINTS:
                raise LifecyclePhaseError(
                    message="仅运行态可生成回答提示",
                    details={"lifecycle_phase": pkg.lifecycle_phase.value},
                )
            if pkg.current_chapter_id != chapter_id or pkg.current_section_id != section_id:
                raise LifecyclePhaseError(
                    message="回答提示仅针对当前指针所在小节",
                    details={
                        "current_chapter_id": pkg.current_chapter_id,
                        "current_section_id": pkg.current_section_id,
                    },
                )

            turns = await self.turns_repo.read_all(scenario_id, chapter_id, section_id)
            awaiting_user = (
                turn_expects_user_reply_active(turns[-1])
                if turns
                else False
            )
            if not awaiting_user:
                raise RuntimeNotAwaitingUserError()

            fw_raw = await self.framework_repo.load_raw(scenario_id)
            if not isinstance(fw_raw, dict):
                raise LifecyclePhaseError(message="缺少 framework.json")
            sf = StoryFrameworkFile.model_validate(fw_raw)
            self._locate_section(sf, chapter_id, section_id)

            self._assert_target_turn(turns, target_turn_id)

            narrative = await self._load_narrative(scenario_id, chapter_id, section_id)
            mission = await self._load_mission(scenario_id, chapter_id, section_id)
            roster = await self._load_roster(scenario_id)

            payload: dict[str, Any] = {
                "scenario_id": scenario_id,
                "chapter_id": chapter_id,
                "section_id": section_id,
                "target_turn_id": target_turn_id,
                "section_narrative": narrative.model_dump(mode="json"),
                "section_mission": mission.model_dump(mode="json"),
                "character_roster": roster.character_roster.model_dump(mode="json"),
                "prior_turns": turns,
            }
            raw = await self.llm.generate_answer_hint_json(payload=payload)
            if not isinstance(raw, dict):
                raise LlmFailureError(message="回答提示 LLM 输出非对象")
            d = self._normalize_hint_dict(
                raw,
                scenario_id=scenario_id,
                chapter_id=chapter_id,
                section_id=section_id,
                linked_turn_id=target_turn_id,
            )
            try:
                out = HintResponse.model_validate(d)
            except ValidationError as e:
                raw2 = await self.llm.generate_answer_hint_json(
                    payload=payload,
                    repair_hint=(
                        "Return flat JSON: scenario_id, chapter_id, section_id, linked_turn_id (=target_turn_id), "
                        "hint_status ready, analysis_markdown 40-12000 chars with ≥1 English sentence on learner goal, "
                        "suggested_utterances: 1-5 English strings each 10-400 chars."
                    ),
                    temperature=0.25,
                )
                if not isinstance(raw2, dict):
                    raise LlmFailureError(message="回答提示修复重试仍失败") from e
                d2 = self._normalize_hint_dict(
                    raw2,
                    scenario_id=scenario_id,
                    chapter_id=chapter_id,
                    section_id=section_id,
                    linked_turn_id=target_turn_id,
                )
                try:
                    out = HintResponse.model_validate(d2)
                except ValidationError as e2:
                    raise LlmFailureError(
                        message="回答提示 JSON 校验失败",
                        details={"errors": str(e2)[:800]},
                    ) from e2

            await self.hints_repo.save_latest(
                scenario_id,
                chapter_id,
                section_id,
                out.model_dump(mode="json"),
            )

        return out

    async def get_hint_latest(
        self,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
    ) -> HintResponse | None:
        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is None:
                raise ScenarioNotFoundError(details={"scenario_id": scenario_id})
            if pkg.lifecycle_phase not in _RUNTIME_HINTS:
                raise LifecyclePhaseError(
                    message="仅运行态可读取回答提示",
                    details={"lifecycle_phase": pkg.lifecycle_phase.value},
                )
            fw_raw = await self.framework_repo.load_raw(scenario_id)
            if not isinstance(fw_raw, dict):
                raise LifecyclePhaseError(message="缺少 framework.json")
            sf = StoryFrameworkFile.model_validate(fw_raw)
            self._locate_section(sf, chapter_id, section_id)

            raw = await self.hints_repo.load_latest(scenario_id, chapter_id, section_id)
            if raw is None:
                return None
            try:
                return HintResponse.model_validate(raw)
            except ValidationError:
                logger.warning("hint_latest.json invalid for %s ch%s sec%s", scenario_id, chapter_id, section_id)
                return None
