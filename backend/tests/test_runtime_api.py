"""运行期 API 测试（M5 / API §4.1 / §4.2）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_runtime_service
from app.main import app


class _OffstageDialogueCallCounter:
    """供离席 roster 名弱校验测试统计 LLM 调用次数。"""

    n: int = 0

    @classmethod
    def reset(cls) -> None:
        cls.n = 0

    @classmethod
    def next(cls) -> int:
        cls.n += 1
        return cls.n


@pytest.fixture
def rt_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setenv("GCP_DATA_DIR", str(d))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    from app import config as config_module
    from app import dependencies as deps_module
    from app.repositories.framework_repo import FrameworkRepo
    from app.repositories.hints_repo import HintsRepo
    from app.repositories.roster_repo import RosterRepo
    from app.repositories.turns_repo import TurnsRepo
    from app.services.runtime_service import RuntimeService

    class FakeLlm:
        async def generate_auto_opener_turn_json(self, *, payload, repair_hint=None, temperature=0.55):
            return {
                "scenario_id": "ignored",
                "chapter_id": 0,
                "section_id": 0,
                "turn_id": "00000000-0000-0000-0000-000000000001",
                "created_at": "2020-01-01T00:00:00Z",
                "speaker_id": payload["opener_speaker_id"],
                "recipient_id": "user",
                "content": "Hello! " * 80,
                "expects_user_response": True,
                "turn_writer": "model_npc",
            }

        async def generate_dialogue_npc_reply_json(self, *, payload, repair_hint=None, temperature=0.55):
            sid = str(payload["scenario_id"])
            sp = str(payload["allowed_npc_speaker_ids"][0])
            return {
                "scenario_id": sid,
                "chapter_id": int(payload["chapter_id"]),
                "section_id": int(payload["section_id"]),
                "turn_id": "00000000-0000-0000-0000-000000000002",
                "created_at": "2020-01-01T00:00:01Z",
                "speaker_id": sp,
                "recipient_id": "user",
                "content": "NPC reply here. " * 10,
                "expects_user_response": True,
                "turn_writer": "model_npc",
            }

    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()

    def _factory() -> RuntimeService:
        pr = deps_module.get_package_repo()
        return RuntimeService(
            package_repo=pr,
            framework_repo=FrameworkRepo(pr.data_dir),
            roster_repo=RosterRepo(pr.data_dir),
            turns_repo=TurnsRepo(pr.data_dir),
            hints_repo=HintsRepo(pr.data_dir),
            llm_client=FakeLlm(),  # type: ignore[arg-type]
        )

    app.dependency_overrides[get_runtime_service] = _factory
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()


def _write_minimal_runtime_tree(root: Path, sid: str) -> None:
    fw = {
        "story_framework": {
            "scenario_id": sid,
            "chapters": [
                {
                    "chapter_id": 1,
                    "chapter_title": "C1",
                    "chapter_summary": "a" * 40,
                    "sections": [
                        {
                            "section_id": 1,
                            "section_title": "S1",
                            "section_summary": "b" * 20,
                        }
                    ],
                }
            ],
        }
    }
    roster = {
        "character_roster": {
            "scenario_id": sid,
            "characters": [
                {
                    "character_id": "user",
                    "name": "U",
                    "role": "r" * 22,
                    "personality": "p" * 22,
                    "is_user": True,
                },
                {
                    "character_id": "npc_a",
                    "name": "A",
                    "role": "r" * 22,
                    "personality": "q" * 22,
                    "is_user": False,
                },
            ],
        }
    }
    nar = {
        "scenario_id": sid,
        "chapter_id": 1,
        "section_id": 1,
        "section_body": "E" * 300,
        "appearing_npc_ids": ["npc_a"],
    }
    mission = {
        "scenario_id": sid,
        "chapter_id": 1,
        "section_id": 1,
        "section_objective": "O" * 40,
    }
    sec_dir = root / "scenarios" / sid / "sections" / "ch1_sec1"
    sec_dir.mkdir(parents=True, exist_ok=True)
    (root / "scenarios" / sid / "framework.json").write_text(
        json.dumps(fw, ensure_ascii=False),
        encoding="utf-8",
    )
    (root / "scenarios" / sid / "roster.json").write_text(
        json.dumps(roster, ensure_ascii=False),
        encoding="utf-8",
    )
    (sec_dir / "narrative.json").write_text(json.dumps(nar, ensure_ascii=False), encoding="utf-8")
    (sec_dir / "mission.json").write_text(json.dumps(mission, ensure_ascii=False), encoding="utf-8")


def test_get_runtime_requires_pointer(rt_client: TestClient, tmp_path: Path) -> None:
    c = rt_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data"
    _write_minimal_runtime_tree(root, sid)
    pkg_path = root / "scenarios" / sid / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "creation_succeeded"
    pdata["current_chapter_id"] = None
    pdata["current_section_id"] = None
    pdata["runtime_awaiting_user"] = None
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")

    r = rt_client.get(f"/api/v1/scenario-packages/{sid}/runtime")
    assert r.status_code == 409
    assert r.json()["error_code"] == "lifecycle_phase_invalid"


def test_enter_then_runtime(rt_client: TestClient, tmp_path: Path) -> None:
    c = rt_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data"
    _write_minimal_runtime_tree(root, sid)
    pkg_path = root / "scenarios" / sid / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "creation_succeeded"
    pdata["current_chapter_id"] = None
    pdata["current_section_id"] = None
    pdata["runtime_awaiting_user"] = None
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")

    e = rt_client.post(f"/api/v1/scenario-packages/{sid}/sections/1/1/enter", json={})
    assert e.status_code == 200, e.text
    body = e.json()
    assert body["lifecycle_phase"] == "runtime_active"
    assert body["auto_opener_triggered"] is True
    assert len(body["turns"]) == 1
    assert body["turns"][0]["speaker_id"] == "npc_a"

    g = rt_client.get(f"/api/v1/scenario-packages/{sid}/runtime")
    assert g.status_code == 200
    assert g.json()["current_chapter_id"] == 1
    assert len(g.json()["turns"]) == 1
    assert g.json()["story_framework_brief"]["chapters"][0]["section_count"] == 1


def test_enter_second_time_no_new_opener(rt_client: TestClient, tmp_path: Path) -> None:
    c = rt_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data"
    _write_minimal_runtime_tree(root, sid)
    pkg_path = root / "scenarios" / sid / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "creation_succeeded"
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")

    rt_client.post(f"/api/v1/scenario-packages/{sid}/sections/1/1/enter", json={})
    e2 = rt_client.post(f"/api/v1/scenario-packages/{sid}/sections/1/1/enter", json={})
    assert e2.status_code == 200
    assert e2.json()["auto_opener_triggered"] is False
    assert len(e2.json()["turns"]) == 1


def test_post_user_turn_after_opener(rt_client: TestClient, tmp_path: Path) -> None:
    c = rt_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data"
    _write_minimal_runtime_tree(root, sid)
    pkg_path = root / "scenarios" / sid / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "creation_succeeded"
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")

    rt_client.post(f"/api/v1/scenario-packages/{sid}/sections/1/1/enter", json={})

    p = rt_client.post(
        f"/api/v1/scenario-packages/{sid}/sections/1/1/turns",
        json={"content": "User line here.", "recipient_id": "npc_a"},
    )
    assert p.status_code == 200, p.text
    body = p.json()
    assert len(body["new_turns"]) == 2
    assert body["new_turns"][0]["speaker_id"] == "user"
    assert body["new_turns"][0]["turn_writer"] == "human_user"
    assert body["new_turns"][1]["turn_writer"] == "model_npc"
    assert body["runtime_awaiting_user"] is True

    g = rt_client.get(f"/api/v1/scenario-packages/{sid}/sections/1/1/turns?limit=1")
    assert g.status_code == 200
    assert len(g.json()["turns"]) == 1
    assert g.json()["turns"][0]["speaker_id"] == "npc_a"


def _write_two_npc_runtime_tree(root: Path, sid: str) -> None:
    fw = {
        "story_framework": {
            "scenario_id": sid,
            "chapters": [
                {
                    "chapter_id": 1,
                    "chapter_title": "C1",
                    "chapter_summary": "a" * 40,
                    "sections": [
                        {
                            "section_id": 1,
                            "section_title": "S1",
                            "section_summary": "b" * 20,
                        }
                    ],
                }
            ],
        }
    }
    roster = {
        "character_roster": {
            "scenario_id": sid,
            "characters": [
                {
                    "character_id": "user",
                    "name": "U",
                    "role": "r" * 22,
                    "personality": "p" * 22,
                    "is_user": True,
                },
                {
                    "character_id": "npc_a",
                    "name": "A",
                    "role": "r" * 22,
                    "personality": "q" * 22,
                    "is_user": False,
                },
                {
                    "character_id": "npc_b",
                    "name": "B",
                    "role": "r" * 22,
                    "personality": "t" * 22,
                    "is_user": False,
                },
            ],
        }
    }
    nar = {
        "scenario_id": sid,
        "chapter_id": 1,
        "section_id": 1,
        "section_body": "E" * 300,
        "appearing_npc_ids": ["npc_a", "npc_b"],
    }
    mission = {
        "scenario_id": sid,
        "chapter_id": 1,
        "section_id": 1,
        "section_objective": "O" * 40,
    }
    sec_dir = root / "scenarios" / sid / "sections" / "ch1_sec1"
    sec_dir.mkdir(parents=True, exist_ok=True)
    (root / "scenarios" / sid / "framework.json").write_text(
        json.dumps(fw, ensure_ascii=False),
        encoding="utf-8",
    )
    (root / "scenarios" / sid / "roster.json").write_text(
        json.dumps(roster, ensure_ascii=False),
        encoding="utf-8",
    )
    (sec_dir / "narrative.json").write_text(json.dumps(nar, ensure_ascii=False), encoding="utf-8")
    (sec_dir / "mission.json").write_text(json.dumps(mission, ensure_ascii=False), encoding="utf-8")


def _write_two_npc_runtime_tree_with_offstage_roster(root: Path, sid: str) -> None:
    """两 NPC 出场 + roster 中另有一名未出场同伴（用于离席 `name` 弱校验测试）。"""
    fw = {
        "story_framework": {
            "scenario_id": sid,
            "chapters": [
                {
                    "chapter_id": 1,
                    "chapter_title": "C1",
                    "chapter_summary": "a" * 40,
                    "sections": [
                        {
                            "section_id": 1,
                            "section_title": "S1",
                            "section_summary": "b" * 20,
                        }
                    ],
                }
            ],
        }
    }
    roster = {
        "character_roster": {
            "scenario_id": sid,
            "characters": [
                {
                    "character_id": "user",
                    "name": "U",
                    "role": "r" * 22,
                    "personality": "p" * 22,
                    "is_user": True,
                },
                {
                    "character_id": "npc_a",
                    "name": "A",
                    "role": "r" * 22,
                    "personality": "q" * 22,
                    "is_user": False,
                },
                {
                    "character_id": "npc_b",
                    "name": "B",
                    "role": "r" * 22,
                    "personality": "t" * 22,
                    "is_user": False,
                },
                {
                    "character_id": "npc_c",
                    "name": "Clara",
                    "role": "r" * 22,
                    "personality": "v" * 22,
                    "is_user": False,
                },
            ],
        }
    }
    nar = {
        "scenario_id": sid,
        "chapter_id": 1,
        "section_id": 1,
        "section_body": "E" * 300,
        "appearing_npc_ids": ["npc_a", "npc_b"],
    }
    mission = {
        "scenario_id": sid,
        "chapter_id": 1,
        "section_id": 1,
        "section_objective": "O" * 40,
    }
    sec_dir = root / "scenarios" / sid / "sections" / "ch1_sec1"
    sec_dir.mkdir(parents=True, exist_ok=True)
    (root / "scenarios" / sid / "framework.json").write_text(
        json.dumps(fw, ensure_ascii=False),
        encoding="utf-8",
    )
    (root / "scenarios" / sid / "roster.json").write_text(
        json.dumps(roster, ensure_ascii=False),
        encoding="utf-8",
    )
    (sec_dir / "narrative.json").write_text(json.dumps(nar, ensure_ascii=False), encoding="utf-8")
    (sec_dir / "mission.json").write_text(json.dumps(mission, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def rt_client_two_npc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setenv("GCP_DATA_DIR", str(d))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    from app import config as config_module
    from app import dependencies as deps_module
    from app.repositories.framework_repo import FrameworkRepo
    from app.repositories.hints_repo import HintsRepo
    from app.repositories.roster_repo import RosterRepo
    from app.repositories.turns_repo import TurnsRepo
    from app.services.runtime_service import RuntimeService

    class FakeLlm:
        async def generate_auto_opener_turn_json(self, *, payload, repair_hint=None, temperature=0.55):
            return {
                "scenario_id": "ignored",
                "chapter_id": 0,
                "section_id": 0,
                "turn_id": "00000000-0000-0000-0000-000000000001",
                "created_at": "2020-01-01T00:00:00Z",
                "speaker_id": payload["opener_speaker_id"],
                "recipient_id": "user",
                "content": "Hello! " * 80,
                "expects_user_response": True,
                "turn_writer": "model_npc",
            }

        async def generate_dialogue_npc_reply_json(self, *, payload, repair_hint=None, temperature=0.55):
            a, b = sorted(payload["allowed_npc_speaker_ids"])
            return {
                "npc_turns": [
                    {
                        "speaker_id": a,
                        "recipient_id": "user",
                        "content": "Ack to user. " * 8,
                        "expects_user_response": False,
                        "turn_writer": "model_npc",
                    },
                    {
                        "speaker_id": a,
                        "recipient_id": b,
                        "content": "A asks B. " * 8,
                        "expects_user_response": False,
                        "turn_writer": "model_npc",
                    },
                    {
                        "speaker_id": b,
                        "recipient_id": "user",
                        "content": "B invites user. " * 8,
                        "expects_user_response": True,
                        "turn_writer": "model_npc",
                    },
                ]
            }

    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()

    def _factory() -> RuntimeService:
        pr = deps_module.get_package_repo()
        return RuntimeService(
            package_repo=pr,
            framework_repo=FrameworkRepo(pr.data_dir),
            roster_repo=RosterRepo(pr.data_dir),
            turns_repo=TurnsRepo(pr.data_dir),
            hints_repo=HintsRepo(pr.data_dir),
            llm_client=FakeLlm(),  # type: ignore[arg-type]
        )

    app.dependency_overrides[get_runtime_service] = _factory
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()


@pytest.fixture
def rt_client_two_npc_offstage_retry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    _OffstageDialogueCallCounter.reset()
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setenv("GCP_DATA_DIR", str(d))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    from app import config as config_module
    from app import dependencies as deps_module
    from app.repositories.framework_repo import FrameworkRepo
    from app.repositories.hints_repo import HintsRepo
    from app.repositories.roster_repo import RosterRepo
    from app.repositories.turns_repo import TurnsRepo
    from app.services.runtime_service import RuntimeService

    class FakeLlm:
        async def generate_auto_opener_turn_json(self, *, payload, repair_hint=None, temperature=0.55):
            return {
                "scenario_id": "ignored",
                "chapter_id": 0,
                "section_id": 0,
                "turn_id": "00000000-0000-0000-0000-000000000001",
                "created_at": "2020-01-01T00:00:00Z",
                "speaker_id": payload["opener_speaker_id"],
                "recipient_id": "user",
                "content": "Hello! " * 80,
                "expects_user_response": True,
                "turn_writer": "model_npc",
            }

        async def generate_dialogue_npc_reply_json(self, *, payload, repair_hint=None, temperature=0.55):
            k = _OffstageDialogueCallCounter.next()
            a, b = sorted(payload["allowed_npc_speaker_ids"])
            if k == 1:
                return {
                    "npc_turns": [
                        {
                            "speaker_id": a,
                            "recipient_id": "user",
                            "content": "Clara could help later. " * 8,
                            "expects_user_response": True,
                            "turn_writer": "model_npc",
                        },
                    ],
                }
            return {
                "npc_turns": [
                    {
                        "speaker_id": a,
                        "recipient_id": "user",
                        "content": "Ack to user. " * 8,
                        "expects_user_response": False,
                        "turn_writer": "model_npc",
                    },
                    {
                        "speaker_id": a,
                        "recipient_id": b,
                        "content": "A asks B. " * 8,
                        "expects_user_response": False,
                        "turn_writer": "model_npc",
                    },
                    {
                        "speaker_id": b,
                        "recipient_id": "user",
                        "content": "B invites user. " * 8,
                        "expects_user_response": True,
                        "turn_writer": "model_npc",
                    },
                ],
            }

    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()

    def _factory() -> RuntimeService:
        pr = deps_module.get_package_repo()
        return RuntimeService(
            package_repo=pr,
            framework_repo=FrameworkRepo(pr.data_dir),
            roster_repo=RosterRepo(pr.data_dir),
            turns_repo=TurnsRepo(pr.data_dir),
            hints_repo=HintsRepo(pr.data_dir),
            llm_client=FakeLlm(),  # type: ignore[arg-type]
        )

    app.dependency_overrides[get_runtime_service] = _factory
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()


def test_post_user_turn_two_npc_batch_chain(rt_client_two_npc: TestClient, tmp_path: Path) -> None:
    c = rt_client_two_npc.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data"
    _write_two_npc_runtime_tree(root, sid)
    pkg_path = root / "scenarios" / sid / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "creation_succeeded"
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")

    rt_client_two_npc.post(f"/api/v1/scenario-packages/{sid}/sections/1/1/enter", json={})

    p = rt_client_two_npc.post(
        f"/api/v1/scenario-packages/{sid}/sections/1/1/turns",
        json={"content": "User to A.", "recipient_id": "npc_a"},
    )
    assert p.status_code == 200, p.text
    body = p.json()
    assert len(body["new_turns"]) == 4
    assert body["new_turns"][0]["speaker_id"] == "user"
    assert body["new_turns"][1]["recipient_id"] == "user"
    assert body["new_turns"][1]["expects_user_response"] is False
    assert body["new_turns"][2]["speaker_id"] != body["new_turns"][2]["recipient_id"]
    assert body["new_turns"][2]["recipient_id"] in ("npc_a", "npc_b")
    assert body["new_turns"][2]["recipient_id"] != "user"
    assert body["new_turns"][3]["recipient_id"] == "user"
    assert body["new_turns"][3]["expects_user_response"] is True
    assert body["runtime_awaiting_user"] is True

    allt = rt_client_two_npc.get(f"/api/v1/scenario-packages/{sid}/sections/1/1/turns")
    assert len(allt.json()["turns"]) == 5


def test_post_user_turn_offstage_roster_name_triggers_retry(
    rt_client_two_npc_offstage_retry: TestClient, tmp_path: Path
) -> None:
    c = rt_client_two_npc_offstage_retry.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data"
    _write_two_npc_runtime_tree_with_offstage_roster(root, sid)
    pkg_path = root / "scenarios" / sid / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "creation_succeeded"
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")

    rt_client_two_npc_offstage_retry.post(f"/api/v1/scenario-packages/{sid}/sections/1/1/enter", json={})

    p = rt_client_two_npc_offstage_retry.post(
        f"/api/v1/scenario-packages/{sid}/sections/1/1/turns",
        json={"content": "User to A.", "recipient_id": "npc_a"},
    )
    assert p.status_code == 200, p.text
    assert _OffstageDialogueCallCounter.n == 2
    body = p.json()
    assert len(body["new_turns"]) == 4
    assert body["runtime_awaiting_user"] is True
    for t in body["new_turns"][1:]:
        assert "Clara" not in t["content"]


def test_auto_opener_retry_when_empty(rt_client: TestClient, tmp_path: Path) -> None:
    c = rt_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data"
    _write_minimal_runtime_tree(root, sid)
    pkg_path = root / "scenarios" / sid / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "runtime_active"
    pdata["current_chapter_id"] = 1
    pdata["current_section_id"] = 1
    pdata["runtime_awaiting_user"] = False
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")

    r = rt_client.post(f"/api/v1/scenario-packages/{sid}/sections/1/1/auto-opener", json={})
    assert r.status_code == 200, r.text
    assert len(r.json()["turns"]) == 1
    assert r.json()["runtime_awaiting_user"] is True


def test_auto_opener_retry_conflict_when_has_turns(rt_client: TestClient, tmp_path: Path) -> None:
    c = rt_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data"
    _write_minimal_runtime_tree(root, sid)
    pkg_path = root / "scenarios" / sid / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "creation_succeeded"
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")

    rt_client.post(f"/api/v1/scenario-packages/{sid}/sections/1/1/enter", json={})
    r = rt_client.post(f"/api/v1/scenario-packages/{sid}/sections/1/1/auto-opener", json={})
    assert r.status_code == 409
    assert r.json()["error_code"] == "section_already_has_turns"
