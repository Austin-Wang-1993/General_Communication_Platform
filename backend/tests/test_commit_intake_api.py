"""commit-intake 集成测试（M2 / API 文档 §2.5）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

VALID_PAYLOAD = {
    "scenario_title": "产品经理周会",
    "user_display_name": "Austin",
    "scene_brief": "x" * 40 + "我在跨境电商做产品，需要主持英文站会。",
    "user_goal_brief": "y" * 10 + "我希望能够用英文流利主持周会。",
    "vocabulary_list": "blocker, alignment",
    "force_reset_creation": False,
}


@pytest.fixture
def intake_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """临时 data_dir + 假 LLM，避免真实调用 DeepSeek。"""
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setenv("GCP_DATA_DIR", str(d))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    from app import config as config_module
    from app import dependencies as deps_module
    from app.dependencies import get_intake_service
    from app.main import app
    from app.repositories.analysis_repo import AnalysisRepo
    from app.repositories.intake_repo import IntakeRepo
    from app.services.intake_service import IntakeService

    class FakeLlm:
        async def expand_intake(self, *, snapshot, repair_hint=None, temperature=0.6):
            return {
                "enriched_scene_description": "E" * 200,
                "enriched_user_goal": "G" * 80,
                "normalized_vocabulary": ["blocker", "alignment"],
            }

    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()

    def _fake_intake() -> IntakeService:
        pr = deps_module.get_package_repo()
        return IntakeService(
            package_repo=pr,
            intake_repo=IntakeRepo(pr.data_dir),
            analysis_repo=AnalysisRepo(pr.data_dir),
            llm_client=FakeLlm(),  # type: ignore[arg-type]
        )

    app.dependency_overrides[get_intake_service] = _fake_intake

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()


def test_commit_intake_not_found(intake_client: TestClient) -> None:
    r = intake_client.post(
        "/api/v1/scenario-packages/00000000-0000-4000-8000-000000000001/commit-intake",
        json=VALID_PAYLOAD,
    )
    assert r.status_code == 404
    assert r.json()["error_code"] == "scenario_not_found"


def test_commit_intake_scene_too_short(intake_client: TestClient) -> None:
    c = intake_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    bad = {**VALID_PAYLOAD, "scene_brief": "短" * 5}
    r = intake_client.post(f"/api/v1/scenario-packages/{sid}/commit-intake", json=bad)
    assert r.status_code == 422
    assert r.json()["error_code"] == "intake_field_too_short"


def test_commit_intake_success_writes_files(intake_client: TestClient, tmp_path: Path) -> None:
    c = intake_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    r = intake_client.post(f"/api/v1/scenario-packages/{sid}/commit-intake", json=VALID_PAYLOAD)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["lifecycle_phase"] == "intake_committed"
    assert body["reset_applied"] is False
    assert len(body["scenario_analysis"]["enriched_scene_description"]) >= 200

    root = tmp_path / "data" / "scenarios" / sid
    assert (root / "intake.json").exists()
    assert (root / "analysis.json").exists()

    g = intake_client.get(f"/api/v1/scenario-packages/{sid}")
    assert g.status_code == 200
    assert g.json()["assets"]["has_intake_snapshot"] is True
    assert g.json()["assets"]["has_scenario_analysis"] is True


def test_commit_intake_framework_requires_force(intake_client: TestClient, tmp_path: Path) -> None:
    c = intake_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    root = tmp_path / "data" / "scenarios" / sid
    (root / "framework.json").write_text("{}", encoding="utf-8")

    r = intake_client.post(f"/api/v1/scenario-packages/{sid}/commit-intake", json=VALID_PAYLOAD)
    assert r.status_code == 409
    assert r.json()["error_code"] == "framework_already_exists"

    r2 = intake_client.post(
        f"/api/v1/scenario-packages/{sid}/commit-intake",
        json={**VALID_PAYLOAD, "force_reset_creation": True},
    )
    assert r2.status_code == 200
    assert r2.json()["reset_applied"] is True
    assert not (root / "framework.json").exists()


def test_commit_intake_lifecycle_running_rejected(intake_client: TestClient, tmp_path: Path) -> None:
    c = intake_client.post("/api/v1/scenario-packages", json={})
    sid = c.json()["scenario_id"]
    pkg_path = tmp_path / "data" / "scenarios" / sid / "package.json"
    data = json.loads(pkg_path.read_text(encoding="utf-8"))
    data["lifecycle_phase"] = "creation_running"
    pkg_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    r = intake_client.post(f"/api/v1/scenario-packages/{sid}/commit-intake", json=VALID_PAYLOAD)
    assert r.status_code == 409
    assert r.json()["error_code"] == "lifecycle_phase_invalid"
