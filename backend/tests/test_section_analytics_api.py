"""R2 本节复盘 API 测试（API §6.1 / §6.2）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_section_analytics_service
from app.main import app


@pytest.fixture
def analytics_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setenv("GCP_DATA_DIR", str(d))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    from app import config as config_module
    from app import dependencies as deps_module
    from app.repositories.framework_repo import FrameworkRepo
    from app.repositories.roster_repo import RosterRepo
    from app.repositories.section_analytics_repo import SectionAnalyticsRepo
    from app.repositories.turns_repo import TurnsRepo
    from app.services.section_analytics_service import SectionAnalyticsService

    class FakeLlm:
        async def generate_section_analytics_json(self, *, payload, repair_hint=None, temperature=0.4):
            tid = str(payload["prior_turns"][-1]["turn_id"])
            sid = str(payload["scenario_id"])
            ch = int(payload["chapter_id"])
            sec = int(payload["section_id"])
            body = (
                "## What went well\n\nYou engaged with the NPC in clear English sentences. "
                "Your tone stayed appropriate for a workplace scenario. "
                "## Main issues\n\nSome phrases could be more natural; watch article usage. "
                "## Next steps\n\nPractice short follow-up questions using present perfect. "
            ) * 3
            assert len(body) >= 200
            return {
                "scenario_id": sid,
                "chapter_id": ch,
                "section_id": sec,
                "evaluated_through_turn_id": tid,
                "section_analytics_status": "ready",
                "holistic_feedback_markdown": body,
                "generated_at": "2020-01-01T00:00:05Z",
            }

    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()

    def _factory() -> SectionAnalyticsService:
        pr = deps_module.get_package_repo()
        return SectionAnalyticsService(
            package_repo=pr,
            framework_repo=FrameworkRepo(pr.data_dir),
            roster_repo=RosterRepo(pr.data_dir),
            turns_repo=TurnsRepo(pr.data_dir),
            analytics_repo=SectionAnalyticsRepo(pr.data_dir),
            llm_client=FakeLlm(),  # type: ignore[arg-type]
        )

    app.dependency_overrides[get_section_analytics_service] = _factory
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()


def _write_tree(root: Path, sid: str) -> None:
    from tests.test_runtime_api import _write_minimal_runtime_tree

    _write_minimal_runtime_tree(root, sid)


def test_section_analytics_no_turns_409(analytics_client: TestClient, tmp_path: Path) -> None:
    c = analytics_client.post("/api/v1/scenario-packages", json={})
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

    r = analytics_client.post(f"/api/v1/scenario-packages/{sid}/sections/1/1/analytics", json={})
    assert r.status_code == 409
    assert r.json()["error_code"] == "section_no_turns_yet"


def test_section_analytics_post_and_get(analytics_client: TestClient, tmp_path: Path) -> None:
    c = analytics_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data"
    _write_tree(root, sid)
    pkg_path = root / "scenarios" / sid / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "runtime_active"
    pdata["current_chapter_id"] = 1
    pdata["current_section_id"] = 1
    pdata["runtime_awaiting_user"] = True
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")

    tid = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    turn = {
        "turn_id": tid,
        "scenario_id": sid,
        "chapter_id": 1,
        "section_id": 1,
        "created_at": "2020-01-01T00:00:00Z",
        "speaker_id": "npc_a",
        "recipient_id": "user",
        "content": "Hello! " * 80,
        "expects_user_response": True,
        "turn_writer": "model_npc",
    }
    sec_dir = root / "scenarios" / sid / "sections" / "ch1_sec1"
    sec_dir.mkdir(parents=True, exist_ok=True)
    (sec_dir / "turns.jsonl").write_text(json.dumps(turn, ensure_ascii=False) + "\n", encoding="utf-8")

    p = analytics_client.post(f"/api/v1/scenario-packages/{sid}/sections/1/1/analytics", json={})
    assert p.status_code == 200, p.text
    body = p.json()
    assert body["section_analytics_status"] == "ready"
    assert body["evaluated_through_turn_id"] == tid
    assert len(body["holistic_feedback_markdown"]) >= 200

    g = analytics_client.get(f"/api/v1/scenario-packages/{sid}/sections/1/1/analytics")
    assert g.status_code == 200
    assert g.json()["linked_turn_id"] == tid
    assert g.json()["section_analytics_status"] == "ready"


def test_section_analytics_get_204(analytics_client: TestClient, tmp_path: Path) -> None:
    c = analytics_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data"
    _write_tree(root, sid)
    pkg_path = root / "scenarios" / sid / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "runtime_active"
    pdata["current_chapter_id"] = 1
    pdata["current_section_id"] = 1
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")

    g = analytics_client.get(f"/api/v1/scenario-packages/{sid}/sections/1/1/analytics")
    assert g.status_code == 204
