"""运行期汇总与进节（API §4.1 / §4.2，中台 §6.6.5）。"""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import ValidationError

from app.clients.llm_client import LlmClient
from app.errors import (
    AutoOpenerFailedError,
    ChapterNotFoundError,
    ContentEmptyOrTooLongError,
    InvalidTurnError,
    LifecyclePhaseError,
    LlmFailureError,
    NpcNpcChainTooLongError,
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
from app.validators.turn_rules import (
    turn_expects_user_reply_active,
    validate_npc_turn_for_append,
    validate_user_turn_for_append,
)

logger = logging.getLogger(__name__)

# 写入 LLM 入参（非持久化）：与 `dialogue_npc_reply.md`、中台 §6.6.6（G）对齐，约束「拆条」与 `expects_user_response` 语义。
NPC_DIALOGUE_RESPONSE_CONTRACT_GUIDE: dict[str, Any] = {
    "expect_recipient_reply_semantics": [
        "Field name is expects_user_response (server schema). When recipient_id is \"user\": "
        "set expects_user_response=true only if the learner must speak next after this line; "
        "set false if this line only wraps up to the learner and the narrative continues with more "
        "npc_turn entries in the same batch (NPC-to-NPC or another NPC line) before asking the learner again.",
        "When recipient_id is an NPC (NPC-to-NPC): expects_user_response MUST be false. "
        "If the story requires that NPC to answer next, add the next array element with speaker_id equal to that recipient_id.",
        "If an NPC first finishes addressing the learner then must address another on-stage NPC, "
        "that MUST be two npc_turn objects (different recipient_id), never one combined speech.",
        "End the batch with recipient_id user and expects_user_response=true so the session waits for the learner "
        "(except single-NPC sections where the batch length is 1 and that line already does so).",
    ],
}

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
        return turn_expects_user_reply_active(turns[-1])

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
                    validate_npc_turn_for_append(
                        turn_d,
                        current_chapter_id=chapter_id,
                        current_section_id=section_id,
                        runtime_awaiting_user=self._awaiting_from_turns([]),
                        prior_turns=[],
                        appearing_npc_ids=narrative.appearing_npc_ids,
                    )
                    await self.turns_repo.append(scenario_id, chapter_id, section_id, turn_d)
                    turns = await self.turns_repo.read_all(scenario_id, chapter_id, section_id)
                    pkg.runtime_awaiting_user = True
                    auto_triggered = True
                    opener_tid = turn.turn_id
                    await self.package_repo.save(pkg)
                except (InvalidTurnError, NpcNpcChainTooLongError):
                    raise
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
            awaiting = self._awaiting_from_turns(turns_before)

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
            validate_user_turn_for_append(
                user_d,
                current_chapter_id=chapter_id,
                current_section_id=section_id,
                runtime_awaiting_user=awaiting,
                prior_turns=turns_before,
                appearing_npc_ids=narrative.appearing_npc_ids,
            )
            await self.turns_repo.append(scenario_id, chapter_id, section_id, user_d)
            pkg.runtime_awaiting_user = False
            pkg.updated_at = utc_now_rfc3339()
            await self.package_repo.save(pkg)
            await self.hints_repo.mark_stale_if_ready(scenario_id, chapter_id, section_id)

            mid_turns = turns_before + [user_d]

            allowed_speakers = set(narrative.appearing_npc_ids)
            npc_payload: dict[str, Any] = {
                "scenario_id": scenario_id,
                "chapter_id": chapter_id,
                "section_id": section_id,
                "section_narrative": narrative.model_dump(mode="json"),
                "section_mission": mission.model_dump(mode="json"),
                "character_roster": roster.character_roster.model_dump(mode="json"),
                "prior_turns": mid_turns,
                "user_turn": user_d,
                "allowed_npc_speaker_ids": sorted(allowed_speakers),
                "response_contract_guide": NPC_DIALOGUE_RESPONSE_CONTRACT_GUIDE,
            }
            try:
                raw_npc = await self.llm.generate_dialogue_npc_reply_json(payload=npc_payload)
                npc_records = self._finalize_parsed_npc_turns(
                    self._parse_npc_reply_turns(
                        raw_npc,
                        scenario_id,
                        chapter_id,
                        section_id,
                        allowed_speakers=allowed_speakers,
                    ),
                    allowed_speakers=allowed_speakers,
                    roster=roster,
                    appearing_npc_ids=narrative.appearing_npc_ids,
                )
                if not npc_records:
                    raw2 = await self.llm.generate_dialogue_npc_reply_json(
                        payload=npc_payload,
                        repair_hint=self._dialogue_npc_repair_hint(allowed_speakers),
                        temperature=0.35,
                    )
                    npc_records = self._finalize_parsed_npc_turns(
                        self._parse_npc_reply_turns(
                            raw2,
                            scenario_id,
                            chapter_id,
                            section_id,
                            allowed_speakers=allowed_speakers,
                        ),
                        allowed_speakers=allowed_speakers,
                        roster=roster,
                        appearing_npc_ids=narrative.appearing_npc_ids,
                    )
                if not npc_records:
                    raise LlmFailureError(message="NPC 续聊 JSON 校验失败")
                try:
                    self._validate_npc_record_batch(
                        npc_records,
                        chapter_id=chapter_id,
                        section_id=section_id,
                        baseline_turns=mid_turns,
                        appearing_npc_ids=narrative.appearing_npc_ids,
                    )
                except (InvalidTurnError, NpcNpcChainTooLongError):
                    raw3 = await self.llm.generate_dialogue_npc_reply_json(
                        payload=npc_payload,
                        repair_hint=self._dialogue_npc_repair_hint(allowed_speakers),
                        temperature=0.25,
                    )
                    npc_records = self._finalize_parsed_npc_turns(
                        self._parse_npc_reply_turns(
                            raw3,
                            scenario_id,
                            chapter_id,
                            section_id,
                            allowed_speakers=allowed_speakers,
                        ),
                        allowed_speakers=allowed_speakers,
                        roster=roster,
                        appearing_npc_ids=narrative.appearing_npc_ids,
                    )
                    if not npc_records:
                        raise LlmFailureError(message="NPC 续聊 JSON 校验失败")
                    self._validate_npc_record_batch(
                        npc_records,
                        chapter_id=chapter_id,
                        section_id=section_id,
                        baseline_turns=mid_turns,
                        appearing_npc_ids=narrative.appearing_npc_ids,
                    )
                for rec in npc_records:
                    await self.turns_repo.append(
                        scenario_id,
                        chapter_id,
                        section_id,
                        rec.model_dump(mode="json"),
                    )
            except LlmFailureError:
                pkg.runtime_awaiting_user = False
                pkg.updated_at = utc_now_rfc3339()
                await self.package_repo.save(pkg)
                raise

            all_turns = await self.turns_repo.read_all(scenario_id, chapter_id, section_id)
            pkg.runtime_awaiting_user = self._awaiting_from_turns(all_turns)
            pkg.updated_at = utc_now_rfc3339()
            await self.package_repo.save(pkg)
            k = len(npc_records)
            new_turns = [user_d] + all_turns[-k:]
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
            validate_npc_turn_for_append(
                turn_d,
                current_chapter_id=chapter_id,
                current_section_id=section_id,
                runtime_awaiting_user=self._awaiting_from_turns([]),
                prior_turns=[],
                appearing_npc_ids=narrative.appearing_npc_ids,
            )
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

    @staticmethod
    def _clip_single_npc_section_batch(
        records: list[TurnRecord],
        allowed_speakers: set[str],
    ) -> list[TurnRecord]:
        if len(allowed_speakers) == 1 and len(records) > 1:
            return records[:1]
        return records

    def _finalize_parsed_npc_turns(
        self,
        parsed: list[TurnRecord],
        *,
        allowed_speakers: set[str],
        roster: CharacterRosterFile,
        appearing_npc_ids: list[str],
    ) -> list[TurnRecord]:
        clipped = self._clip_single_npc_section_batch(parsed, allowed_speakers)
        if clipped and not self._npc_turn_batch_passes_roster_stage_lock(
            clipped, roster, appearing_npc_ids
        ):
            return []
        return clipped

    @staticmethod
    def _offstage_roster_display_names(
        roster: CharacterRosterFile,
        appearing_npc_ids: list[str],
    ) -> list[str]:
        on_stage = set(appearing_npc_ids)
        names: list[str] = []
        seen: set[str] = set()
        for c in roster.character_roster.characters:
            if c.is_user or c.character_id in on_stage:
                continue
            n = c.name.strip()
            if len(n) < 3 or n.lower() in seen:
                continue
            seen.add(n.lower())
            names.append(n)
        names.sort(key=len, reverse=True)
        return names

    @staticmethod
    def _content_mentions_display_name(content: str, name: str) -> bool:
        if not name:
            return False
        pat = r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])"
        return re.search(pat, content, flags=re.IGNORECASE) is not None

    @staticmethod
    def _npc_turn_batch_passes_roster_stage_lock(
        records: list[TurnRecord],
        roster: CharacterRosterFile,
        appearing_npc_ids: list[str],
    ) -> bool:
        forbidden = RuntimeService._offstage_roster_display_names(roster, appearing_npc_ids)
        if not forbidden:
            return True
        for rec in records:
            text = rec.content
            for name in forbidden:
                if RuntimeService._content_mentions_display_name(text, name):
                    logger.info(
                        "npc_turns rejected: roster peer %r not in appearing_npc_ids appears in content",
                        name,
                    )
                    return False
        return True

    @staticmethod
    def _dialogue_npc_repair_hint(allowed_speakers: set[str]) -> str:
        ids = ", ".join(sorted(allowed_speakers))
        return (
            "Follow input.response_contract_guide for split turns and expects_user_response rules. "
            "Return JSON with root key npc_turns: array of 1 to 3 objects. "
            "Each object MUST have keys: speaker_id, recipient_id, content, expects_user_response, turn_writer (model_npc). "
            f"speaker_id and recipient_id (when not user) MUST be chosen ONLY from: {ids} and user. "
            "speaker_id must never be user. speaker_id and recipient_id must differ. "
            "Each content addresses ONLY that object's recipient — no 'UserName, ... Mark, ...' in one line; split into separate objects. "
            "Do NOT invent on-stage characters not in appearing_npc_ids from input section_narrative. "
            "Do NOT spell the display names of roster characters whose character_id is NOT in appearing_npc_ids "
            "(off-stage peers); refer generically if needed. "
            "When recipient_id is user, do not embed imperative lines clearly meant for another on-stage NPC in the same bubble; "
            "use a separate npc_turn with recipient_id set to that NPC. "
            "For NPC-to-NPC lines set recipient_id to the other NPC and expects_user_response false. "
            "The LAST object in npc_turns MUST have recipient_id user and expects_user_response true so the learner can reply. "
            "If only one NPC is on stage, npc_turns length MUST be 1."
        )

    @staticmethod
    def _npc_turn_dicts_from_llm(raw: object) -> list[dict[str, Any]]:
        if not isinstance(raw, dict):
            return []
        nt = raw.get("npc_turns")
        if isinstance(nt, list) and nt:
            return [dict(x) for x in nt if isinstance(x, dict)][:3]
        return [dict(raw)]

    def _validate_npc_record_batch(
        self,
        records: list[TurnRecord],
        *,
        chapter_id: int,
        section_id: int,
        baseline_turns: list[dict[str, Any]],
        appearing_npc_ids: list[str],
    ) -> None:
        prior = list(baseline_turns)
        for rec in records:
            rd = rec.model_dump(mode="json")
            awaiting = self._awaiting_from_turns(prior)
            validate_npc_turn_for_append(
                rd,
                current_chapter_id=chapter_id,
                current_section_id=section_id,
                runtime_awaiting_user=awaiting,
                prior_turns=prior,
                appearing_npc_ids=appearing_npc_ids,
            )
            prior.append(rd)

    def _parse_npc_reply_turns(
        self,
        raw: object,
        scenario_id: str,
        chapter_id: int,
        section_id: int,
        *,
        allowed_speakers: set[str],
    ) -> list[TurnRecord]:
        out: list[TurnRecord] = []
        for d in self._npc_turn_dicts_from_llm(raw):
            rec = self._parse_one_npc_dict_into_turn(
                d,
                scenario_id,
                chapter_id,
                section_id,
                allowed_speakers=allowed_speakers,
            )
            if rec is None:
                return []
            out.append(rec)
        return out

    def _parse_one_npc_dict_into_turn(
        self,
        d_raw: dict[str, Any],
        scenario_id: str,
        chapter_id: int,
        section_id: int,
        *,
        allowed_speakers: set[str],
    ) -> TurnRecord | None:
        d = dict(d_raw)
        if "npc_turn" in d and isinstance(d["npc_turn"], dict):
            d = dict(d["npc_turn"])
        if "turn" in d and isinstance(d["turn"], dict):
            d = dict(d["turn"])
        sp = str(d.get("speaker_id", "")).strip()
        if sp not in allowed_speakers:
            sp = sorted(allowed_speakers)[0] if allowed_speakers else ""
        rp = str(d.get("recipient_id", "user")).strip() or "user"
        if rp != "user" and rp not in allowed_speakers:
            rp = "user"
        if sp == rp:
            rp = "user"
        exp_raw = d.get("expects_user_response", False)
        if isinstance(exp_raw, bool):
            exp = exp_raw
        else:
            exp = str(exp_raw).lower() in ("true", "1", "yes")
        content = str(d.get("content", "")).strip()
        if not content or len(content) > 8000:
            return None
        now = utc_now_rfc3339()
        try:
            return TurnRecord.model_validate(
                {
                    "scenario_id": scenario_id,
                    "chapter_id": chapter_id,
                    "section_id": section_id,
                    "turn_id": new_turn_id(),
                    "created_at": now,
                    "speaker_id": sp,
                    "recipient_id": rp,
                    "content": content,
                    "expects_user_response": exp,
                    "turn_writer": TurnWriter.MODEL_NPC,
                }
            )
        except ValidationError:
            return None
