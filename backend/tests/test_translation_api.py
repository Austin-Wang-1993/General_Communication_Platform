"""英译中辅助接口测试（中台 §6.9）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_translation_service
from app.main import app
from app.services.translation_service import TranslationService


@pytest.fixture
def translate_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setenv("GCP_DATA_DIR", str(d))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    from app import config as config_module
    from app import dependencies as deps_module

    class FakeLlm:
        async def translate_line_en_to_zh(self, *, source_text: str, temperature: float = 0.25) -> str:
            return f"译：{source_text[:40]}"

    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()

    def _factory() -> TranslationService:
        return TranslationService(llm_client=FakeLlm())  # type: ignore[arg-type]

    app.dependency_overrides[get_translation_service] = _factory
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()


def test_translate_en_to_zh_ok(translate_client: TestClient) -> None:
    r = translate_client.post("/api/v1/translation/en-to-zh", json={"text": "Hello world."})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["translated_text"].startswith("译：")


def test_translate_en_to_zh_empty(translate_client: TestClient) -> None:
    r = translate_client.post("/api/v1/translation/en-to-zh", json={"text": "   "})
    assert r.status_code == 422
