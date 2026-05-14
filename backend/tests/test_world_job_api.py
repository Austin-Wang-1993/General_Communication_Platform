"""World Job API 测试（M4 / API §3.2 / §3.4）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_framework_job_service, get_world_job_service
from app.main import app
from app.repositories.analysis_repo import AnalysisRepo
from app.repositories.framework_repo import FrameworkRepo
from app.repositories.intake_repo import IntakeRepo
from app.repositories.job_repo import JobRepo
from app.repositories.roster_repo import RosterRepo
from app.services.framework_job_service import FrameworkJobService
from app.services.world_job_service import WorldJobService


@pytest.fixture
def m4_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[TestClient, dict]:
    """临时 data_dir + 假 LLM（framework + world）。"""
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setenv("GCP_DATA_DIR", str(d))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    from app import config as config_module
    from app import dependencies as deps_module

    class FakeLlm:
        async def generate_story_framework_json(self, *, payload, repair_hint=None, temperature=0.45):
            sid = str(payload["scenario_id"])
            return {
                "story_framework": {
                    "scenario_id": sid,
                    "chapters": [
                        {
                            "chapter_id": 1,
                            "chapter_title": "Chapter One",
                            "chapter_summary": "a" * 40,
                            "sections": [
                                {
                                    "section_id": 1,
                                    "section_title": "Opening",
                                    "section_summary": "b" * 20,
                                }
                            ],
                        }
                    ],
                }
            }

        async def generate_character_roster_json(self, *, payload, repair_hint=None, temperature=0.45):
            sid = str(payload["scenario_id"])
            return {
                "character_roster": {
                    "scenario_id": sid,
                    "characters": [
                        {
                            "character_id": "user",
                            "name": "Hero",
                            "role": "Product lead in meeting context",
                            "personality": "p" * 22,
                            "is_user": True,
                        },
                        {
                            "character_id": "npc_a",
                            "name": "Alex",
                            "role": "Senior engineer in standup",
                            "personality": "q" * 22,
                            "is_user": False,
                        },
                    ],
                }
            }

        async def generate_section_narrative_json(self, *, payload, repair_hint=None, temperature=0.45):
            return {
                "scenario_id": str(payload["scenario_id"]),
                "chapter_id": int(payload["chapter_id"]),
                "section_id": int(payload["section_id"]),
                "section_body": "E" * 320,
                "appearing_npc_ids": ["npc_a"],
            }

        async def generate_section_mission_json(self, *, payload, repair_hint=None, temperature=0.45):
            return {
                "scenario_id": str(payload["scenario_id"]),
                "chapter_id": int(payload["chapter_id"]),
                "section_id": int(payload["section_id"]),
                "section_objective": "O" * 50,
            }

    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()

    fake = FakeLlm()
    holder: dict = {"fw": None, "world": None}

    def _fw_factory() -> FrameworkJobService:
        pr = deps_module.get_package_repo()
        s = FrameworkJobService(
            package_repo=pr,
            job_repo=JobRepo(pr.data_dir),
            framework_repo=FrameworkRepo(pr.data_dir),
            roster_repo=RosterRepo(pr.data_dir),
            intake_repo=IntakeRepo(pr.data_dir),
            analysis_repo=AnalysisRepo(pr.data_dir),
            llm_client=fake,  # type: ignore[arg-type]
        )
        holder["fw"] = s
        return s

    def _world_factory() -> WorldJobService:
        pr = deps_module.get_package_repo()
        w = WorldJobService(
            package_repo=pr,
            job_repo=JobRepo(pr.data_dir),
            framework_repo=FrameworkRepo(pr.data_dir),
            roster_repo=RosterRepo(pr.data_dir),
            analysis_repo=AnalysisRepo(pr.data_dir),
            llm_client=fake,  # type: ignore[arg-type]
        )
        holder["world"] = w
        return w

    app.dependency_overrides[get_framework_job_service] = _fw_factory
    app.dependency_overrides[get_world_job_service] = _world_factory

    with TestClient(app) as client:
        yield client, holder

    app.dependency_overrides.clear()
    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()


def _seed_intake_committed(client: TestClient, tmp_path: Path) -> str:
    c = client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data" / "scenarios" / sid
    (root / "intake.json").write_text(
        json.dumps(
            {
                "scenario_id": sid,
                "user_display_name": "Austin",
                "scene_brief": "x",
                "user_goal_brief": "y",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "analysis.json").write_text(
        json.dumps(
            {
                "scenario_id": sid,
                "enriched_scene_description": "e" * 200,
                "enriched_user_goal": "g" * 80,
                "normalized_vocabulary": ["ok"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    pkg_path = root / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "intake_committed"
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")
    return sid


@pytest.mark.asyncio
async def test_world_job_success_writes_sections(
    m4_client: tuple[TestClient, dict],
    tmp_path: Path,
) -> None:
    client, holder = m4_client
    sid = _seed_intake_committed(client, tmp_path)
    r0 = client.post(f"/api/v1/scenario-packages/{sid}/jobs/framework", json={})
    assert r0.status_code == 202
    job_fw = r0.json()["job_id"]
    await holder["fw"].run_framework_pipeline(sid, job_fw)

    r = client.post(f"/api/v1/scenario-packages/{sid}/jobs/world", json={})
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    await holder["world"].run_world_pipeline(sid, job_id)

    g = client.get(f"/api/v1/scenario-packages/{sid}/jobs/{job_id}")
    assert g.status_code == 200
    assert g.json()["status"] == "succeeded"

    root = tmp_path / "data" / "scenarios" / sid
    assert (root / "sections" / "ch1_sec1" / "narrative.json").exists()
    assert (root / "sections" / "ch1_sec1" / "mission.json").exists()
    pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
    assert pkg["lifecycle_phase"] == "creation_succeeded"


@pytest.mark.asyncio
async def test_world_job_sections_already_exist(
    m4_client: tuple[TestClient, dict],
    tmp_path: Path,
) -> None:
    client, holder = m4_client
    sid = _seed_intake_committed(client, tmp_path)
    r0 = client.post(f"/api/v1/scenario-packages/{sid}/jobs/framework", json={})
    job_fw = r0.json()["job_id"]
    await holder["fw"].run_framework_pipeline(sid, job_fw)

    r1 = client.post(f"/api/v1/scenario-packages/{sid}/jobs/world", json={})
    job_w = r1.json()["job_id"]
    await holder["world"].run_world_pipeline(sid, job_w)

    r2 = client.post(f"/api/v1/scenario-packages/{sid}/jobs/world", json={"force_regenerate": False})
    assert r2.status_code == 409
    assert r2.json()["error_code"] == "sections_already_exist"


def test_cancel_world_clears_sections(m4_client: tuple[TestClient, dict], tmp_path: Path) -> None:
    client, _ = m4_client
    sid = _seed_intake_committed(client, tmp_path)
    root = tmp_path / "data" / "scenarios" / sid
    jid = "22222222-2222-4222-8222-222222222222"
    jobs_dir = root / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    (jobs_dir / f"{jid}.json").write_text(
        json.dumps(
            {
                "job_id": jid,
                "type": "world",
                "scenario_id": sid,
                "status": "running",
                "current_step_label": "…",
                "progress_hint": "1/1",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "finished_at": None,
                "error_code": None,
                "error_message": None,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    sec = root / "sections" / "ch1_sec1"
    sec.mkdir(parents=True)
    (sec / "narrative.json").write_text("{}", encoding="utf-8")

    pkg_path = root / "package.json"
    pdata = json.loads(pkg_path.read_text(encoding="utf-8"))
    pdata["lifecycle_phase"] = "creation_running"
    pkg_path.write_text(json.dumps(pdata, ensure_ascii=False), encoding="utf-8")

    r = client.post(f"/api/v1/scenario-packages/{sid}/jobs/{jid}/cancel")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cleared_assets"] == ["sections"]
    assert body["lifecycle_phase_after"] == "intake_committed"
    assert not (root / "sections" / "ch1_sec1" / "narrative.json").exists()


@pytest.mark.asyncio
async def test_cancel_job_already_terminal(
    m4_client: tuple[TestClient, dict],
    tmp_path: Path,
) -> None:
    client, holder = m4_client
    sid = _seed_intake_committed(client, tmp_path)
    r0 = client.post(f"/api/v1/scenario-packages/{sid}/jobs/framework", json={})
    jid = r0.json()["job_id"]
    await holder["fw"].run_framework_pipeline(sid, jid)

    r = client.post(f"/api/v1/scenario-packages/{sid}/jobs/{jid}/cancel")
    assert r.status_code == 409
    assert r.json()["error_code"] == "job_already_terminal"
