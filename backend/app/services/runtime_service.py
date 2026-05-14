"""运行期汇总与进节（API §4.1 / §4.2，PRD §6.6.5）。"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from app.clients.llm_client import LlmClient
from app.errors import (
    AutoOpenerFailedError,
    ChapterNotFoundError,
    LifecyclePhaseError,
    LlmFailureError,
    ScenarioNotFoundError,
    SectionNotFoundError,
)
from app.lib.clock import utc_now_rfc3339
from app.lib.ids import new_turn_id
from app.models.enums import LifecyclePhase, TurnWriter
from app.models.runtime_api import (
    EnterSectionResponse,
    RuntimeResponse,
    StoryFrameworkBrief,
    StoryFrameworkBriefChapter,
)
from app.models.section_assets import SectionMissionPayload, SectionNarrativePayload
from app.models.story_assets import CharacterRosterFile, StoryFrameworkFile
from app.models.turns import TurnRecord
from app.repositories.base import get_scenario_lock, read_json
from app.repositories.framework_repo import FrameworkRepo
from app.repositories.package_repo import PackageRepo
from app.repositories.roster_repo import RosterRepo
from app.repositories.turns_repo import TurnsRepo

logger = logging.getLogger(__name__)

_ALLOWED_READ = frozenset({LifecyclePhase.CREATION_SUCCEEDED, LifecyclePhase.RUNTIME_ACTIVE})


class RuntimeService:
    def __init__(
        self,
        *,
        package_repo: PackageRepo,
        framework_repo: FrameworkRepo,
        roster_repo: RosterRepo,
        turns_repo: TurnsRepo,
        llm_client: LlmClient,
    ) -> None:
        self.package_repo = package_repo
        self.framework_repo = framework_repo
        self.roster_repo = roster_repo
        self.turns_repo = turns_repo
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

    def _framework_brief(self, sf: StoryFrameworkFile) -> StoryFrameworkBrief:
        chs: list[StoryFrameworkBriefChapter] = []
        for ch in sf.story_framework.chapters:
            chs.append(
                StoryFrameworkBriefChapter(
                    chapter_id=ch.chapter_id,
                    chapter_title=ch.chapter_title,
                    section_count=len(ch.sections),
                )
            )
        return StoryFrameworkBrief(chapters=chs)

    @staticmethod
    def _awaiting_from_turns(turns: list[dict[str, Any]]) -> bool:
        if not turns:
            return False
        return bool(turns[-1].get("expects_user_response"))

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

    async def get_runtime(self, scenario_id: str) -> RuntimeResponse:
        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is None:
                raise ScenarioNotFoundError(details={"scenario_id": scenario_id})
            if pkg.lifecycle_phase not in _ALLOWED_READ:
                raise LifecyclePhaseError(
                    message="当前生命周期不允许读取运行态",
                    details={"lifecycle_phase": pkg.lifecycle_phase.value},
                )
            if pkg.current_chapter_id is None or pkg.current_section_id is None:
                raise LifecyclePhaseError(
                    message="运行指针未设置",
                    details={
                        "lifecycle_phase": pkg.lifecycle_phase.value,
                        "hint": "请先调用 POST /api/v1/scenario-packages/{id}/sections/{ch}/{sec}/enter",
                    },
                )
            ch, sec = pkg.current_chapter_id, pkg.current_section_id

            fw_raw = await self.framework_repo.load_raw(scenario_id)
            if not isinstance(fw_raw, dict):
                raise LifecyclePhaseError(message="缺少 framework.json")
            sf = StoryFrameworkFile.model_validate(fw_raw)
            self._locate_section(sf, ch, sec)

            narrative = await self._load_narrative(scenario_id, ch, sec)
            mission = await self._load_mission(scenario_id, ch, sec)
            roster = await self._load_roster(scenario_id)
            turns = await self.turns_repo.read_all(scenario_id, ch, sec)
            brief = self._framework_brief(sf)
            awaiting = self._awaiting_from_turns(turns)

        return RuntimeResponse(
            scenario_id=scenario_id,
            lifecycle_phase=pkg.lifecycle_phase,
            current_chapter_id=ch,
            current_section_id=sec,
            runtime_awaiting_user=awaiting,
            section_narrative=narrative.model_dump(mode="json"),
            section_mission=mission.model_dump(mode="json"),
            character_roster=roster.character_roster.model_dump(mode="json"),
            turns=turns,
            story_framework_brief=brief,
        )

    async def enter_section(
        self,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
    ) -> EnterSectionResponse:
        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is None:
                raise ScenarioNotFoundError(details={"scenario_id": scenario_id})
            if pkg.lifecycle_phase not in _ALLOWED_READ:
                raise LifecyclePhaseError(
                    message="当前生命周期不允许进节",
                    details={"lifecycle_phase": pkg.lifecycle_phase.value},
                )

            fw_raw = await self.framework_repo.load_raw(scenario_id)
            if not isinstance(fw_raw, dict):
                raise LifecyclePhaseError(message="缺少 framework.json")
            sf = StoryFrameworkFile.model_validate(fw_raw)
            self._locate_section(sf, chapter_id, section_id)

            narrative = await self._load_narrative(scenario_id, chapter_id, section_id)
            mission = await self._load_mission(scenario_id, chapter_id, section_id)
            roster = await self._load_roster(scenario_id)

            pkg.current_chapter_id = chapter_id
            pkg.current_section_id = section_id
            if pkg.lifecycle_phase == LifecyclePhase.CREATION_SUCCEEDED:
                pkg.lifecycle_phase = LifecyclePhase.RUNTIME_ACTIVE
            pkg.updated_at = utc_now_rfc3339()

            turns = await self.turns_repo.read_all(scenario_id, chapter_id, section_id)
            auto_triggered = False
            opener_tid: str | None = None

            if turns:
                pkg.runtime_awaiting_user = self._awaiting_from_turns(turns)
                await self.package_repo.save(pkg)
            else:
                try:
                    turn = await self._generate_auto_opener(
                        scenario_id=scenario_id,
                        chapter_id=chapter_id,
                        section_id=section_id,
                        narrative=narrative,
                        mission=mission,
                        roster=roster,
                    )
                    turn_d = turn.model_dump(mode="json")
                    await self.turns_repo.append(scenario_id, chapter_id, section_id, turn_d)
                    turns = await self.turns_repo.read_all(scenario_id, chapter_id, section_id)
                    pkg.runtime_awaiting_user = True
                    auto_triggered = True
                    opener_tid = turn.turn_id
                    await self.package_repo.save(pkg)
                except (LlmFailureError, ValidationError) as e:
                    logger.warning("auto opener failed: %s", e)
                    pkg.runtime_awaiting_user = False
                    await self.package_repo.save(pkg)
                    raise AutoOpenerFailedError(
                        details={
                            "cause": getattr(e, "error_code", type(e).__name__),
                            "message": str(e)[:500],
                        },
                    ) from e

            brief_roster = roster.character_roster.model_dump(mode="json")

        return EnterSectionResponse(
            scenario_id=scenario_id,
            current_chapter_id=chapter_id,
            current_section_id=section_id,
            lifecycle_phase=pkg.lifecycle_phase,
            runtime_awaiting_user=bool(pkg.runtime_awaiting_user),
            section_narrative=narrative.model_dump(mode="json"),
            section_mission=mission.model_dump(mode="json"),
            character_roster=brief_roster,
            turns=turns,
            auto_opener_triggered=auto_triggered,
            auto_opener_turn_id=opener_tid,
        )

    async def _generate_auto_opener(
        self,
        *,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
        narrative: SectionNarrativePayload,
        mission: SectionMissionPayload,
        roster: CharacterRosterFile,
    ) -> TurnRecord:
        opener_npc = narrative.appearing_npc_ids[0]
        payload: dict[str, Any] = {
            "scenario_id": scenario_id,
            "chapter_id": chapter_id,
            "section_id": section_id,
            "section_narrative": narrative.model_dump(mode="json"),
            "section_mission": mission.model_dump(mode="json"),
            "character_roster": roster.character_roster.model_dump(mode="json"),
            "opener_speaker_id": opener_npc,
        }
        raw = await self.llm.generate_auto_opener_turn_json(payload=payload)
        rec = self._parse_opener_turn(raw, scenario_id, chapter_id, section_id, opener_npc)
        if rec is None:
            raw2 = await self.llm.generate_auto_opener_turn_json(
                payload=payload,
                repair_hint=(
                    "Return ONE flat JSON object with keys: scenario_id, chapter_id, section_id, "
                    "turn_id, created_at, speaker_id, recipient_id, content, expects_user_response, turn_writer. "
                    "speaker_id must equal opener_speaker_id from input. recipient_id must be user. "
                    "expects_user_response true. turn_writer model_npc. content: English 1-8000 chars, NPC speaks to user."
                ),
                temperature=0.35,
            )
            rec = self._parse_opener_turn(raw2, scenario_id, chapter_id, section_id, opener_npc)
        if rec is None:
            raise AutoOpenerFailedError(details={"reason": "turn_json_invalid"})
        return rec

    def _parse_opener_turn(
        self,
        raw: object,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
        opener_speaker_id: str,
    ) -> TurnRecord | None:
        if not isinstance(raw, dict):
            return None
        d = dict(raw)
        if "turn" in d and isinstance(d["turn"], dict):
            d = dict(d["turn"])
        now = utc_now_rfc3339()
        d["scenario_id"] = scenario_id
        d["chapter_id"] = chapter_id
        d["section_id"] = section_id
        d["turn_id"] = new_turn_id()
        d["created_at"] = now
        d["speaker_id"] = opener_speaker_id
        d["recipient_id"] = "user"
        d["expects_user_response"] = True
        d["turn_writer"] = TurnWriter.MODEL_NPC.value
        try:
            return TurnRecord.model_validate(d)
        except ValidationError:
            return None
