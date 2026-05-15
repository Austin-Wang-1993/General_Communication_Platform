"""PRD §6.6.4 回合硬规则校验（纯函数，业务流程见 `04-业务流程与状态机.md` §4）。"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from app.errors import InvalidTurnError, NpcNpcChainTooLongError, RuntimeNotAwaitingUserError

USER = "user"


def turn_expects_user_reply_active(t: Mapping[str, Any]) -> bool:
    """与 `RuntimeService._awaiting_from_turns` 一致：本条是否把运行态置于「等待用户下一条发言」。

    仅将 **显式真值** 视为 True（避免 JSON 里字符串 `"false"` 被 Python `bool("false")` 误判为 True）。
    """
    v = t.get("expects_user_response")
    if v is True:
        return True
    if isinstance(v, str) and v.strip().lower() in ("true", "1", "yes"):
        return True
    return False


def is_npc_npc_turn(t: Mapping[str, Any]) -> bool:
    """§6.6.4 规则 6：双方均非练习者。"""
    return t.get("speaker_id") != USER and t.get("recipient_id") != USER


def trailing_npc_npc_count(turns: list[Mapping[str, Any]]) -> int:
    """当前 `turns` 末尾连续 NPC–NPC 条数 L（§6.6.4 规则 7）。"""
    n = 0
    for t in reversed(turns):
        if is_npc_npc_turn(t):
            n += 1
        else:
            break
    return n


def _rule0_pointer(
    turn: Mapping[str, Any],
    *,
    current_chapter_id: int,
    current_section_id: int,
) -> None:
    ch = turn.get("chapter_id")
    sec = turn.get("section_id")
    if ch != current_chapter_id or sec != current_section_id:
        raise InvalidTurnError(
            message="回合的小节指针与当前运行指针不一致",
            details={
                "rule": 0,
                "current_chapter_id": current_chapter_id,
                "current_section_id": current_section_id,
                "turn_chapter_id": ch,
                "turn_section_id": sec,
            },
        )


def validate_user_turn_for_append(
    turn: Mapping[str, Any],
    *,
    current_chapter_id: int,
    current_section_id: int,
    runtime_awaiting_user: bool,
    prior_turns: list[Mapping[str, Any]],
    appearing_npc_ids: Collection[str],
) -> None:
    """用户回合写入前校验（规则 0、1 及与上一条的衔接）。"""
    _rule0_pointer(turn, current_chapter_id=current_chapter_id, current_section_id=current_section_id)

    if not runtime_awaiting_user:
        raise RuntimeNotAwaitingUserError()

    if not prior_turns:
        raise RuntimeNotAwaitingUserError(
            details={"reason": "no_turns_yet_use_enter_or_auto_opener"},
        )
    last = prior_turns[-1]
    if not turn_expects_user_reply_active(last):
        raise RuntimeNotAwaitingUserError(
            details={"reason": "last_turn_not_expecting_user"},
        )

    if turn.get("turn_writer") != "human_user":
        raise InvalidTurnError(
            details={"rule": 1, "field": "turn_writer", "expected": "human_user", "got": turn.get("turn_writer")},
        )
    if turn.get("speaker_id") != USER:
        raise InvalidTurnError(
            details={"rule": 1, "field": "speaker_id", "expected": USER, "got": turn.get("speaker_id")},
        )

    rid = turn.get("recipient_id")
    allowed = set(appearing_npc_ids)
    if rid not in allowed:
        raise InvalidTurnError(
            message="用户回合的 recipient_id 须为本节 appearing_npc_ids 之一",
            details={"rule": 1, "recipient_id": rid, "allowed": sorted(allowed)},
        )
    if rid == USER:
        raise InvalidTurnError(
            details={"rule": 1, "recipient_id": rid},
        )

    if turn.get("expects_user_response") is True:
        raise InvalidTurnError(
            message="用户发言回合的 expects_user_response 须为 false",
            details={"rule": 1, "field": "expects_user_response"},
        )


def validate_npc_turn_for_append(
    turn: Mapping[str, Any],
    *,
    current_chapter_id: int,
    current_section_id: int,
    runtime_awaiting_user: bool,
    prior_turns: list[Mapping[str, Any]],
    appearing_npc_ids: Collection[str],
) -> None:
    """NPC（model_npc）回合写入前校验（规则 0、1、2、3、6、7 等）。"""
    _rule0_pointer(turn, current_chapter_id=current_chapter_id, current_section_id=current_section_id)

    if runtime_awaiting_user:
        raise InvalidTurnError(
            message="等待用户回应期间不得写入 NPC 回合（§6.6.4 规则 1）",
            details={"rule": 1, "runtime_awaiting_user": True},
        )

    if turn.get("turn_writer") != "model_npc":
        raise InvalidTurnError(
            details={"field": "turn_writer", "expected": "model_npc", "got": turn.get("turn_writer")},
        )
    sp = turn.get("speaker_id")
    rp = turn.get("recipient_id")
    if sp == USER:
        raise InvalidTurnError(
            details={"field": "speaker_id", "reason": "model_npc_speaker_cannot_be_user"},
        )

    allowed_speakers = set(appearing_npc_ids)
    allowed_recipients = allowed_speakers | {USER}
    if sp not in allowed_speakers:
        raise InvalidTurnError(
            message="speaker_id 须为本节 appearing_npc_ids 之一",
            details={"rule": 5, "speaker_id": sp, "allowed": sorted(allowed_speakers)},
        )
    if rp not in allowed_recipients:
        raise InvalidTurnError(
            message="recipient_id 须为 user 或本节 NPC",
            details={"rule": 5, "recipient_id": rp},
        )
    if sp == rp:
        raise InvalidTurnError(
            details={"rule": 5, "speaker_id": sp, "recipient_id": rp},
        )

    exp = turn.get("expects_user_response")
    if exp is True and rp != USER:
        raise InvalidTurnError(
            message="expects_user_response 为 true 时 recipient_id 必须为 user（§6.6.4 规则 2）",
            details={"rule": 2},
        )

    if len(appearing_npc_ids) == 2 and is_npc_npc_turn(turn) and exp is True:
        raise InvalidTurnError(
            message="双 NPC 小节中 NPC–NPC 回合的 expects_user_response 须为 false（§6.6.4 规则 3）",
            details={"rule": 3},
        )

    if is_npc_npc_turn(turn):
        l_tail = trailing_npc_npc_count(list(prior_turns))
        if l_tail + 1 > 3:
            raise NpcNpcChainTooLongError(
                details={"rule": 7, "trailing_npc_npc_count": l_tail},
            )
