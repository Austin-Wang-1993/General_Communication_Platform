"""场景包路由集成测试（M1 / API 文档 §2.1 ~ §2.4）。

每个 case 用独立临时 data_dir，互不污染。
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_list_empty_when_no_packages(app_client: TestClient) -> None:
    r = app_client.get("/api/v1/scenario-packages")
    assert r.status_code == 200
    assert r.json() == {"packages": []}


def test_create_empty_package_returns_draft(app_client: TestClient) -> None:
    r = app_client.post("/api/v1/scenario-packages", json={})
    assert r.status_code == 201
    body = r.json()

    assert body["lifecycle_phase"] == "draft"
    assert body["scenario_title"] == ""
    assert body["created_at"].endswith("Z")
    assert body["updated_at"].endswith("Z")
    # UUID v4 36 字符
    assert len(body["scenario_id"]) == 36


def test_create_with_title_hint(app_client: TestClient) -> None:
    r = app_client.post(
        "/api/v1/scenario-packages",
        json={"scenario_title_hint": "  我的英语练习  "},
    )
    assert r.status_code == 201
    body = r.json()
    # 修剪首尾空白
    assert body["scenario_title"] == "我的英语练习"


def test_create_without_body_is_allowed(app_client: TestClient) -> None:
    r = app_client.post("/api/v1/scenario-packages")
    assert r.status_code == 201
    assert r.json()["lifecycle_phase"] == "draft"


def test_create_title_hint_too_long_rejected(app_client: TestClient) -> None:
    r = app_client.post(
        "/api/v1/scenario-packages",
        json={"scenario_title_hint": "x" * 121},
    )
    # FastAPI/Pydantic 422 校验失败
    assert r.status_code == 422


def test_get_nonexistent_returns_404(app_client: TestClient) -> None:
    r = app_client.get("/api/v1/scenario-packages/not-exist-id")
    assert r.status_code == 404
    body = r.json()
    assert body["error_code"] == "scenario_not_found"
    assert "message" in body


def test_get_existing_returns_summary_with_assets(app_client: TestClient, temp_data_dir: Path) -> None:
    create = app_client.post("/api/v1/scenario-packages", json={})
    scenario_id = create.json()["scenario_id"]

    r = app_client.get(f"/api/v1/scenario-packages/{scenario_id}")
    assert r.status_code == 200
    body = r.json()

    assert body["scenario_id"] == scenario_id
    assert body["lifecycle_phase"] == "draft"
    assert body["current_chapter_id"] is None
    assert body["current_section_id"] is None
    assert body["runtime_awaiting_user"] is None
    # assets：M1 阶段全为 false / 0
    assert body["assets"] == {
        "has_intake_snapshot": False,
        "has_scenario_analysis": False,
        "has_story_framework": False,
        "has_character_roster": False,
        "section_assets_count": 0,
        "section_assets_complete": False,
    }


def test_list_returns_packages_sorted_by_updated_at_desc(app_client: TestClient) -> None:
    # 创建 3 个包；按 created/updated 时间天然递增
    ids = [
        app_client.post("/api/v1/scenario-packages", json={}).json()["scenario_id"]
        for _ in range(3)
    ]

    r = app_client.get("/api/v1/scenario-packages")
    assert r.status_code == 200
    packages = r.json()["packages"]
    assert len(packages) == 3
    listed_ids = [p["scenario_id"] for p in packages]

    # 最新创建的在前；放宽：所有 3 个都在结果集
    assert set(listed_ids) == set(ids)
    # 至少前两个应该是按 updated_at 降序——由于秒级粒度可能相同，做容错断言
    times = [p["updated_at"] for p in packages]
    assert times == sorted(times, reverse=True)


def test_delete_existing_returns_204(app_client: TestClient) -> None:
    create = app_client.post("/api/v1/scenario-packages", json={})
    scenario_id = create.json()["scenario_id"]

    r = app_client.delete(f"/api/v1/scenario-packages/{scenario_id}")
    assert r.status_code == 204
    # 再次 GET 应返回 404
    r2 = app_client.get(f"/api/v1/scenario-packages/{scenario_id}")
    assert r2.status_code == 404


def test_delete_nonexistent_returns_404(app_client: TestClient) -> None:
    r = app_client.delete("/api/v1/scenario-packages/never-existed")
    assert r.status_code == 404
    assert r.json()["error_code"] == "scenario_not_found"


def test_data_truly_persists_on_disk(app_client: TestClient, temp_data_dir: Path) -> None:
    create = app_client.post("/api/v1/scenario-packages", json={"scenario_title_hint": "落盘测试"})
    scenario_id = create.json()["scenario_id"]

    package_json = temp_data_dir / "scenarios" / scenario_id / "package.json"
    assert package_json.exists(), "package.json 必须真的写到磁盘上"

    import json
    content = json.loads(package_json.read_text(encoding="utf-8"))
    assert content["scenario_id"] == scenario_id
    assert content["scenario_title"] == "落盘测试"
    assert content["lifecycle_phase"] == "draft"
