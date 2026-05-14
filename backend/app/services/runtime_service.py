"""运行期汇总与进节（API §4.1 / §4.2，PRD §6.6.5）。"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from app.clients.llm_client import LlmClient
from app.errors import (
    AutoOpenerFailedError,
    ChapterNotFoundError,
    ContentEmptyOrTooLongError,
    LifecyclePhaseError,
    LlmFailureError,
    RecipientIdInvalidError,
    RuntimeNotAwaitingUserError,
    ScenarioNotFoundError,
    SectionAlreadyHasTurnsError,
    SectionNotFoundError,
)
from app.lib.clock import utc_now_rfc3339
from app.lib.ids import new_turn_id
from app.models.enums import LifecyclePhase, TurnWriter
from app.models.runtime_api import (
    AutoOpenerRetryResponse,
    EnterSectionResponse,
    PostUserTurnResponse,
    RuntimeResponse,
    SectionTurnsListResponse,
    StoryFrameworkBrief,
    StoryFrameworkBriefChapter,
)
from app.models.section_assets import SectionMissionPayload, SectionNarrativePayload
from app.models.story_assets import CharacterRosterFile, StoryFrameworkFile
from app.models.turns import TurnRecord
from app.repositories.base import get_scenario_lock, read_json
from app.repositories.framework_repo import FrameworkRepo
from app.repositories.hints_repo import HintsRepo
from app.repositories.package_repo import PackageRepo
from app.repositories.roster_repo import RosterRepo
from app.repositories.turns_repo import TurnsRepo

logger = logging.getLogger(__name__)

_ALLOWED_READ = frozenset({LifecyclePhase.CREATION_SUCCEEDED, LifecyclePhase.RUNTIME_ACTIVE})
_RUNTIME_POST_TURNS = frozenset({LifecyclePhase.RUNTIME_ACTIVE})


class RuntimeService:
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

    async def get_section_turns(
        self,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
        *,
        limit: int | None = None,
    ) -> SectionTurnsListResponse:
        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is None:
                raise ScenarioNotFoundError(details={"scenario_id": scenario_id})
            fw_raw = await self.framework_repo.load_raw(scenario_id)
            if not isinstance(fw_raw, dict):
                raise LifecyclePhaseError(message="缺少 framework.json")
            sf = StoryFrameworkFile.model_validate(fw_raw)
            self._locate_section(sf, chapter_id, section_id)
            turns = await self.turns_repo.read_all(scenario_id, chapter_id, section_id, limit=limit)
        return SectionTurnsListResponse(
            scenario_id=scenario_id,
            chapter_id=chapter_id,
            section_id=section_id,
            turns=turns,
        )

    async def post_user_turn(
        self,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
        *,
        content: str,
        recipient_id: str,
    ) -> PostUserTurnResponse:
        text = content.strip()
        if not text:
            raise ContentEmptyOrTooLongError(details={"field": "content"})
        if len(text) > 8000:
            raise ContentEmptyOrTooLongError(details={"field": "content", "length": len(text)})

        rid = recipient_id.strip()
        if rid == "user":
            raise RecipientIdInvalidError(details={"recipient_id": rid})

        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is None:
                raise ScenarioNotFoundError(details={"scenario_id": scenario_id})
            if pkg.lifecycle_phase not in _RUNTIME_POST_TURNS:
                raise LifecyclePhaseError(
                    message="仅运行态可发送用户回合",
                    details={"lifecycle_phase": pkg.lifecycle_phase.value},
                )
            if pkg.current_chapter_id != chapter_id or pkg.current_section_id != section_id:
                raise LifecyclePhaseError(
                    message="只能向当前指针所在小节写入回合",
                    details={
                        "current_chapter_id": pkg.current_chapter_id,
                        "current_section_id": pkg.current_section_id,
                        "requested_chapter_id": chapter_id,
                        "requested_section_id": section_id,
                    },
                )
            if not pkg.runtime_awaiting_user:
                raise RuntimeNotAwaitingUserError()

            fw_raw = await self.framework_repo.load_raw(scenario_id)
            if not isinstance(fw_raw, dict):
                raise LifecyclePhaseError(message="缺少 framework.json")
            sf = StoryFrameworkFile.model_validate(fw_raw)
            self._locate_section(sf, chapter_id, section_id)

            narrative = await self._load_narrative(scenario_id, chapter_id, section_id)
            mission = await self._load_mission(scenario_id, chapter_id, section_id)
            roster = await self._load_roster(scenario_id)
            allowed_recipients = set(narrative.appearing_npc_ids)
            if rid not in allowed_recipients:
                raise RecipientIdInvalidError(
                    details={"recipient_id": rid, "allowed": sorted(allowed_recipients)},
                )

            turns_before = await self.turns_repo.read_all(scenario_id, chapter_id, section_id)
            if not turns_before:
                raise RuntimeNotAwaitingUserError(
                    details={"reason": "no_turns_yet_use_enter_or_auto_opener"},
                )
            last = turns_before[-1]
            if not last.get("expects_user_response"):
                raise RuntimeNotAwaitingUserError(
                    details={"reason": "last_turn_not_expecting_user"},
                )

            now = utc_now_rfc3339()
            user_turn = TurnRecord(
                scenario_id=scenario_id,
                chapter_id=chapter_id,
                section_id=section_id,
                turn_id=new_turn_id(),
                created_at=now,
                speaker_id="user",
                recipient_id=rid,
                content=text,
                expects_user_response=False,
                turn_writer=TurnWriter.HUMAN_USER,
            )
            user_d = user_turn.model_dump(mode="json")
            await self.turns_repo.append(scenario_id, chapter_id, section_id, user_d)
            await self.hints_repo.mark_stale_if_ready(scenario_id, chapter_id, section_id)

            allowed_speakers = set(narrative.appearing_npc_ids)
            npc_payload: dict[str, Any] = {
                "scenario_id": scenario_id,
                "chapter_id": chapter_id,
                "section_id": section_id,
                "section_narrative": narrative.model_dump(mode="json"),
                "section_mission": mission.model_dump(mode="json"),
                "character_roster": roster.character_roster.model_dump(mode="json"),
                "prior_turns": turns_before + [user_d],
                "user_turn": user_d,
                "allowed_npc_speaker_ids": sorted(allowed_speakers),
            }
            try:
                raw_npc = await self.llm.generate_dialogue_npc_reply_json(payload=npc_payload)
                npc_rec = self._parse_npc_reply_turn(
                    raw_npc,
                    scenario_id,
                    chapter_id,
                    section_id,
                    allowed_speakers=allowed_speakers,
                )
                if npc_rec is None:
                    raw2 = await self.llm.generate_dialogue_npc_reply_json(
                        payload=npc_payload,
                        repair_hint=(
                            "Return ONE flat JSON turn: speaker_id must be one of allowed_npc_speaker_ids; "
                            "recipient_id user; expects_user_response true; turn_writer model_npc; "
                            "content English 1-8000 chars."
                        ),
                        temperature=0.35,
                    )
                    npc_rec = self._parse_npc_reply_turn(
                        raw2,
                        scenario_id,
                        chapter_id,
                        section_id,
                        allowed_speakers=allowed_speakers,
                    )
                if npc_rec is None:
                    raise LlmFailureError(message="NPC 续聊 JSON 校验失败")
                npc_d = npc_rec.model_dump(mode="json")
                await self.turns_repo.append(scenario_id, chapter_id, section_id, npc_d)
            except LlmFailureError:
                pkg.runtime_awaiting_user = False
                pkg.updated_at = utc_now_rfc3339()
                await self.package_repo.save(pkg)
                raise

            all_turns = await self.turns_repo.read_all(scenario_id, chapter_id, section_id)
            pkg.runtime_awaiting_user = self._awaiting_from_turns(all_turns)
            pkg.updated_at = utc_now_rfc3339()
            await self.package_repo.save(pkg)
            new_turns = [user_d, all_turns[-1]]
            awaiting = bool(pkg.runtime_awaiting_user)

        return PostUserTurnResponse(new_turns=new_turns, runtime_awaiting_user=awaiting)

    async def retry_section_auto_opener(
        self,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
    ) -> AutoOpenerRetryResponse:
        async with get_scenario_lock(scenario_id):
            pkg = await self.package_repo.load(scenario_id)
            if pkg is None:
                raise ScenarioNotFoundError(details={"scenario_id": scenario_id})
            if pkg.lifecycle_phase not in _ALLOWED_READ:
                raise LifecyclePhaseError(
                    message="当前生命周期不允许自动开场重试",
                    details={"lifecycle_phase": pkg.lifecycle_phase.value},
                )
            if pkg.current_chapter_id != chapter_id or pkg.current_section_id != section_id:
                raise LifecyclePhaseError(
                    message="只能对当前指针所在小节重试自动开场",
                    details={
                        "current_chapter_id": pkg.current_chapter_id,
                        "current_section_id": pkg.current_section_id,
                    },
                )

            turns = await self.turns_repo.read_all(scenario_id, chapter_id, section_id)
            if turns:
                raise SectionAlreadyHasTurnsError(details={"turn_count": len(turns)})

            narrative = await self._load_narrative(scenario_id, chapter_id, section_id)
            mission = await self._load_mission(scenario_id, chapter_id, section_id)
            roster = await self._load_roster(scenario_id)

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
            all_turns = await self.turns_repo.read_all(scenario_id, chapter_id, section_id)
            pkg.runtime_awaiting_user = True
            pkg.updated_at = utc_now_rfc3339()
            await self.package_repo.save(pkg)

        return AutoOpenerRetryResponse(
            turn=turn_d,
            turns=all_turns,
            runtime_awaiting_user=True,
        )

    def _parse_npc_reply_turn(
        self,
        raw: object,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
        *,
        allowed_speakers: set[str],
    ) -> TurnRecord | None:
        if not isinstance(raw, dict):
            return None
        d = dict(raw)
        if "npc_turn" in d and isinstance(d["npc_turn"], dict):
            d = dict(d["npc_turn"])
        if "turn" in d and isinstance(d["turn"], dict):
            d = dict(d["turn"])
        sp = str(d.get("speaker_id", "")).strip()
        if sp not in allowed_speakers:
            sp = sorted(allowed_speakers)[0] if allowed_speakers else ""
        now = utc_now_rfc3339()
        d["scenario_id"] = scenario_id
        d["chapter_id"] = chapter_id
        d["section_id"] = section_id
        d["turn_id"] = new_turn_id()
        d["created_at"] = now
        d["speaker_id"] = sp
        d["recipient_id"] = "user"
        d["expects_user_response"] = True
        d["turn_writer"] = TurnWriter.MODEL_NPC.value
        try:
            return TurnRecord.model_validate(d)
        except ValidationError:
            return None
