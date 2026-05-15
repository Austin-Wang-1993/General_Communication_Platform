"""§6.6.4 回合规则纯函数测试（validators/turn_rules.py）。"""

from __future__ import annotations

import pytest

from app.errors import InvalidTurnError, NpcNpcChainTooLongError, RuntimeNotAwaitingUserError
from app.validators.turn_rules import (
    is_npc_npc_turn,
    trailing_npc_npc_count,
    turn_expects_user_reply_active,
    validate_npc_turn_for_append,
    validate_user_turn_for_append,
)


def test_is_npc_npc_turn() -> None:
    assert is_npc_npc_turn({"speaker_id": "a", "recipient_id": "b"}) is True
    assert is_npc_npc_turn({"speaker_id": "user", "recipient_id": "b"}) is False
    assert is_npc_npc_turn({"speaker_id": "a", "recipient_id": "user"}) is False


def test_trailing_npc_npc_count() -> None:
    t = [
        {"speaker_id": "user", "recipient_id": "a"},
        {"speaker_id": "a", "recipient_id": "b"},
        {"speaker_id": "b", "recipient_id": "a"},
        {"speaker_id": "a", "recipient_id": "b"},
    ]
    assert trailing_npc_npc_count(t) == 3


def test_turn_expects_user_reply_active_coerces_string() -> None:
    assert turn_expects_user_reply_active({"expects_user_response": True}) is True
    assert turn_expects_user_reply_active({"expects_user_response": False}) is False
    assert turn_expects_user_reply_active({"expects_user_response": "false"}) is False
    assert turn_expects_user_reply_active({"expects_user_response": "true"}) is True
    assert turn_expects_user_reply_active({}) is False


def test_validate_user_turn_ok() -> None:
    prior = [
        {
            "speaker_id": "npc_a",
            "recipient_id": "user",
            "expects_user_response": True,
            "turn_writer": "model_npc",
        }
    ]
    turn = {
        "chapter_id": 1,
        "section_id": 1,
        "speaker_id": "user",
        "recipient_id": "npc_a",
        "expects_user_response": False,
        "turn_writer": "human_user",
    }
    validate_user_turn_for_append(
        turn,
        current_chapter_id=1,
        current_section_id=1,
        runtime_awaiting_user=True,
        prior_turns=prior,
        appearing_npc_ids=["npc_a"],
    )


def test_validate_user_turn_not_awaiting() -> None:
    with pytest.raises(RuntimeNotAwaitingUserError):
        validate_user_turn_for_append(
            {
                "chapter_id": 1,
                "section_id": 1,
                "speaker_id": "user",
                "recipient_id": "npc_a",
                "expects_user_response": False,
                "turn_writer": "human_user",
            },
            current_chapter_id=1,
            current_section_id=1,
            runtime_awaiting_user=False,
            prior_turns=[{"expects_user_response": True}],
            appearing_npc_ids=["npc_a"],
        )


def test_validate_npc_rule_seven_blocks_fourth() -> None:
    prior = [
        {"speaker_id": "a", "recipient_id": "b", "turn_writer": "model_npc"},
        {"speaker_id": "b", "recipient_id": "a", "turn_writer": "model_npc"},
        {"speaker_id": "a", "recipient_id": "b", "turn_writer": "model_npc"},
    ]
    candidate = {
        "chapter_id": 1,
        "section_id": 1,
        "speaker_id": "b",
        "recipient_id": "a",
        "expects_user_response": False,
        "turn_writer": "model_npc",
    }
    with pytest.raises(NpcNpcChainTooLongError):
        validate_npc_turn_for_append(
            candidate,
            current_chapter_id=1,
            current_section_id=1,
            runtime_awaiting_user=False,
            prior_turns=prior,
            appearing_npc_ids=["a", "b"],
        )


def test_validate_npc_rule_three_dual_npc_expects_true() -> None:
    candidate = {
        "chapter_id": 1,
        "section_id": 1,
        "speaker_id": "npc_a",
        "recipient_id": "npc_b",
        "expects_user_response": True,
        "turn_writer": "model_npc",
    }
    with pytest.raises(InvalidTurnError):
        validate_npc_turn_for_append(
            candidate,
            current_chapter_id=1,
            current_section_id=1,
            runtime_awaiting_user=False,
            prior_turns=[],
            appearing_npc_ids=["npc_a", "npc_b"],
        )


def test_validate_rule_zero_pointer() -> None:
    with pytest.raises(InvalidTurnError) as ei:
        validate_user_turn_for_append(
            {
                "chapter_id": 2,
                "section_id": 1,
                "speaker_id": "user",
                "recipient_id": "npc_a",
                "expects_user_response": False,
                "turn_writer": "human_user",
            },
            current_chapter_id=1,
            current_section_id=1,
            runtime_awaiting_user=True,
            prior_turns=[{"expects_user_response": True}],
            appearing_npc_ids=["npc_a"],
        )
    assert ei.value.details and ei.value.details.get("rule") == 0
