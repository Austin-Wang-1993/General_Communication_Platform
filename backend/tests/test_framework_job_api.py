"""Framework Job API 测试（M3 / API §3.1 / §3.3）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_framework_job_service
from app.main import app
from app.repositories.analysis_repo import AnalysisRepo
from app.repositories.framework_repo import FrameworkRepo
from app.repositories.intake_repo import IntakeRepo
from app.repositories.job_repo import JobRepo
from app.repositories.roster_repo import RosterRepo
from app.services.framework_job_service import FrameworkJobService


@pytest.fixture
def fw_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[TestClient, dict]:
    """临时 data_dir + 假 LLM；返回 (client, {"svc": FrameworkJobService | None})。"""
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

    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()

    holder: dict = {"svc": None}

    def _factory() -> FrameworkJobService:
        pr = deps_module.get_package_repo()
        s = FrameworkJobService(
            package_repo=pr,
            job_repo=JobRepo(pr.data_dir),
            framework_repo=FrameworkRepo(pr.data_dir),
            roster_repo=RosterRepo(pr.data_dir),
            intake_repo=IntakeRepo(pr.data_dir),
            analysis_repo=AnalysisRepo(pr.data_dir),
            llm_client=FakeLlm(),  # type: ignore[arg-type]
        )
        holder["svc"] = s
        return s

    app.dependency_overrides[get_framework_job_service] = _factory

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
async def test_framework_job_success_writes_assets(
    fw_client: tuple[TestClient, dict],
    tmp_path: Path,
) -> None:
    client, holder = fw_client
    sid = _seed_intake_committed(client, tmp_path)
    r = client.post(f"/api/v1/scenario-packages/{sid}/jobs/framework", json={})
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    svc: FrameworkJobService = holder["svc"]
    assert svc is not None
    await svc.run_framework_pipeline(sid, job_id)

    g = client.get(f"/api/v1/scenario-packages/{sid}/jobs/{job_id}")
    assert g.status_code == 200
    assert g.json()["status"] == "succeeded"

    root = tmp_path / "data" / "scenarios" / sid
    assert (root / "framework.json").exists()
    assert (root / "roster.json").exists()
    pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
    assert pkg["lifecycle_phase"] == "intake_committed"


def test_framework_job_conflict_when_running(fw_client: tuple[TestClient, dict], tmp_path: Path) -> None:
    client, _holder = fw_client
    sid = _seed_intake_committed(client, tmp_path)
    jobs_dir = tmp_path / "data" / "scenarios" / sid / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    stale = {
        "job_id": "11111111-1111-4111-8111-111111111111",
        "type": "framework",
        "scenario_id": sid,
        "status": "running",
        "current_step_label": "…",
        "progress_hint": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "finished_at": None,
        "error_code": None,
        "error_message": None,
    }
    (jobs_dir / f"{stale['job_id']}.json").write_text(json.dumps(stale), encoding="utf-8")

    r2 = client.post(f"/api/v1/scenario-packages/{sid}/jobs/framework", json={})
    assert r2.status_code == 409
    assert r2.json()["error_code"] == "active_job_conflict"


def test_framework_job_wrong_phase(fw_client: tuple[TestClient, dict], tmp_path: Path) -> None:
    client, _ = fw_client
    c = client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    r = client.post(f"/api/v1/scenario-packages/{sid}/jobs/framework", json={})
    assert r.status_code == 409
    assert r.json()["error_code"] == "lifecycle_phase_invalid"


def test_get_job_not_found(fw_client: tuple[TestClient, dict], tmp_path: Path) -> None:
    client, _ = fw_client
    sid = _seed_intake_committed(client, tmp_path)
    r = client.get(f"/api/v1/scenario-packages/{sid}/jobs/00000000-0000-4000-8000-000000000001")
    assert r.status_code == 404
    assert r.json()["error_code"] == "job_not_found"
