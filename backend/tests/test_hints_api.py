"""R1 回答提示 API 测试（API §5.1 / §5.2）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_hints_service, get_runtime_service
from app.main import app


@pytest.fixture
def hint_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
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
    from app.services.hints_service import HintsService
    from app.services.runtime_service import RuntimeService

    class FakeLlm:
        async def generate_auto_opener_turn_json(self, *, payload, repair_hint=None, temperature=0.55):
            return {
                "scenario_id": "ignored",
                "chapter_id": 0,
                "section_id": 0,
                "turn_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
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
                "turn_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "created_at": "2020-01-01T00:00:01Z",
                "speaker_id": sp,
                "recipient_id": "user",
                "content": "NPC reply here. " * 10,
                "expects_user_response": True,
                "turn_writer": "model_npc",
            }

        async def generate_answer_hint_json(self, *, payload, repair_hint=None, temperature=0.45):
            tid = str(payload["target_turn_id"])
            sid = str(payload["scenario_id"])
            ch = int(payload["chapter_id"])
            sec = int(payload["section_id"])
            analysis = (
                "This is an English sentence about your communication goal here. "
                "You should respond clearly and politely to the NPC question above. "
            )
            assert len(analysis) >= 40
            return {
                "scenario_id": sid,
                "chapter_id": ch,
                "section_id": sec,
                "linked_turn_id": tid,
                "hint_status": "ready",
                "analysis_markdown": analysis,
                "suggested_utterances": [
                    "Could you elaborate on that point in more detail please?",
                    "I would like to hear your view on how we should proceed next.",
                ],
                "generated_at": "2020-01-01T00:00:02Z",
            }

    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()

    def _rt() -> RuntimeService:
        pr = deps_module.get_package_repo()
        return RuntimeService(
            package_repo=pr,
            framework_repo=FrameworkRepo(pr.data_dir),
            roster_repo=RosterRepo(pr.data_dir),
            turns_repo=TurnsRepo(pr.data_dir),
            hints_repo=HintsRepo(pr.data_dir),
            llm_client=FakeLlm(),  # type: ignore[arg-type]
        )

    def _hi() -> HintsService:
        pr = deps_module.get_package_repo()
        return HintsService(
            package_repo=pr,
            framework_repo=FrameworkRepo(pr.data_dir),
            roster_repo=RosterRepo(pr.data_dir),
            turns_repo=TurnsRepo(pr.data_dir),
            hints_repo=HintsRepo(pr.data_dir),
            llm_client=FakeLlm(),  # type: ignore[arg-type]
        )

    app.dependency_overrides[get_runtime_service] = _rt
    app.dependency_overrides[get_hints_service] = _hi
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()


def _write_tree(root: Path, sid: str) -> None:
    from tests.test_runtime_api import _write_minimal_runtime_tree

    _write_minimal_runtime_tree(root, sid)


def test_hints_latest_204(hint_client: TestClient, tmp_path: Path) -> None:
    c = hint_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data"
    _write_tree(root, sid)
    pkg_path = root / "scenarios" / sid / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "runtime_active"
    pdata["current_chapter_id"] = 1
    pdata["current_section_id"] = 1
    pdata["runtime_awaiting_user"] = False
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")

    r = hint_client.get(f"/api/v1/scenario-packages/{sid}/sections/1/1/hints/latest")
    assert r.status_code == 204


def test_post_hint_and_latest_then_stale_after_turn(hint_client: TestClient, tmp_path: Path) -> None:
    c = hint_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data"
    _write_tree(root, sid)
    pkg_path = root / "scenarios" / sid / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "creation_succeeded"
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")

    e = hint_client.post(f"/api/v1/scenario-packages/{sid}/sections/1/1/enter", json={})
    assert e.status_code == 200, e.text
    opener_tid = e.json()["turns"][0]["turn_id"]

    h = hint_client.post(
        f"/api/v1/scenario-packages/{sid}/sections/1/1/hints",
        json={"target_turn_id": opener_tid},
    )
    assert h.status_code == 200, h.text
    assert h.json()["hint_status"] == "ready"
    assert len(h.json()["suggested_utterances"]) >= 1

    g = hint_client.get(f"/api/v1/scenario-packages/{sid}/sections/1/1/hints/latest")
    assert g.status_code == 200
    assert g.json()["linked_turn_id"] == opener_tid

    p = hint_client.post(
        f"/api/v1/scenario-packages/{sid}/sections/1/1/turns",
        json={"content": "User speaks here.", "recipient_id": "npc_a"},
    )
    assert p.status_code == 200, p.text

    g2 = hint_client.get(f"/api/v1/scenario-packages/{sid}/sections/1/1/hints/latest")
    assert g2.status_code == 200
    assert g2.json()["hint_status"] == "stale"
    assert g2.json()["analysis_markdown"] == ""
    assert g2.json()["suggested_utterances"] == []


def test_post_hint_wrong_turn_id(hint_client: TestClient, tmp_path: Path) -> None:
    c = hint_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data"
    _write_tree(root, sid)
    pkg_path = root / "scenarios" / sid / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "creation_succeeded"
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")

    hint_client.post(f"/api/v1/scenario-packages/{sid}/sections/1/1/enter", json={})

    h = hint_client.post(
        f"/api/v1/scenario-packages/{sid}/sections/1/1/hints",
        json={"target_turn_id": "00000000-0000-0000-0000-000000000099"},
    )
    assert h.status_code == 404
    assert h.json()["error_code"] == "turn_not_found"
