"""WorldJobService 小节 narrative 的 appearing_npc_ids 清洗逻辑（单元）。"""

from __future__ import annotations

from app.services.world_job_service import WorldJobService


def test_sanitize_npc_ids_truncates_to_two_in_order() -> None:
    allowed = {"npc_a", "npc_b", "npc_c", "npc_d"}
    assert WorldJobService._sanitize_appearing_npc_ids(
        ["npc_a", "npc_b", "npc_c", "npc_d"],
        allowed,
    ) == ["npc_a", "npc_b"]


def test_sanitize_npc_ids_skips_invalid_keeps_order() -> None:
    allowed = {"npc_x", "npc_y"}
    assert WorldJobService._sanitize_appearing_npc_ids(
        ["bad", "npc_y", "  ", "npc_x"],
        allowed,
    ) == ["npc_y", "npc_x"]


def test_sanitize_npc_ids_empty_returns_none() -> None:
    assert WorldJobService._sanitize_appearing_npc_ids([], {"a"}) is None
    assert WorldJobService._sanitize_appearing_npc_ids(["only_bad"], {"a"}) is None
    assert WorldJobService._sanitize_appearing_npc_ids("not-a-list", {"a"}) is None
