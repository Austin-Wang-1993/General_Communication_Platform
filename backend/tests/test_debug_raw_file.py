"""GET /api/v1/debug/raw-file（§7.2）。"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


def test_raw_file_returns_json(app_client: TestClient, temp_data_dir: Path) -> None:
    sid = str(uuid.uuid4())
    pkg = temp_data_dir / "scenarios" / sid
    pkg.mkdir(parents=True)
    payload = {"ok": True, "scenario_id": sid}
    (pkg / "framework.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    response = app_client.get("/api/v1/debug/raw-file", params={"scenario_id": sid, "relpath": "framework.json"})
    assert response.status_code == 200
    assert response.json() == payload


def test_raw_file_not_whitelisted(app_client: TestClient, temp_data_dir: Path) -> None:
    sid = str(uuid.uuid4())
    (temp_data_dir / "scenarios" / sid).mkdir(parents=True)
    response = app_client.get("/api/v1/debug/raw-file", params={"scenario_id": sid, "relpath": "secrets.env"})
    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_request_body"


def test_raw_file_rejects_path_traversal(app_client: TestClient, temp_data_dir: Path) -> None:
    sid = str(uuid.uuid4())
    (temp_data_dir / "scenarios" / sid).mkdir(parents=True)
    response = app_client.get("/api/v1/debug/raw-file", params={"scenario_id": sid, "relpath": "../framework.json"})
    assert response.status_code == 400


def test_raw_file_not_found(app_client: TestClient, temp_data_dir: Path) -> None:
    sid = str(uuid.uuid4())
    (temp_data_dir / "scenarios" / sid).mkdir(parents=True)
    response = app_client.get("/api/v1/debug/raw-file", params={"scenario_id": sid, "relpath": "framework.json"})
    assert response.status_code == 404
    assert response.json()["error_code"] == "raw_file_not_found"


def test_raw_file_section_narrative(app_client: TestClient, temp_data_dir: Path) -> None:
    sid = str(uuid.uuid4())
    pkg = temp_data_dir / "scenarios" / sid
    sec = pkg / "sections" / "ch1_sec1"
    sec.mkdir(parents=True)
    payload = {"scenario_id": sid, "chapter_id": 1, "section_id": 1, "section_body": "x", "appearing_npc_ids": ["a"]}
    (sec / "narrative.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    response = app_client.get(
        "/api/v1/debug/raw-file",
        params={"scenario_id": sid, "relpath": "sections/ch1_sec1/narrative.json"},
    )
    assert response.status_code == 200
    assert response.json()["section_body"] == "x"
