"""pytest 公共 fixtures。

主要解决：让被测的 FastAPI app 使用一个临时数据目录，不污染开发机器上的 data/。
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """每个测试一个全新临时目录。"""
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def app_client(temp_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """覆盖 GCP_DATA_DIR 环境变量并构造 TestClient。

    通过 monkeypatch 注入临时目录，并清空 settings 单例，让 get_settings() 重新读取。
    """
    # 注：必须在 import app 之前覆盖环境变量，但已有模块 import 会被缓存。
    # 故先 patch env，再 reload 相关单例。
    monkeypatch.setenv("GCP_DATA_DIR", str(temp_data_dir))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")  # 测试不需要

    from app import config as config_module
    from app import dependencies as deps_module

    # 清掉 settings 与 repo 单例缓存
    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()

    # 此处再 import main.app 不会被模块级语句重置环境（main 在 startup 才读）
    from app.main import app

    with TestClient(app) as client:
        yield client

    # 清理缓存，避免污染下一个测试
    config_module._settings = None  # type: ignore[attr-defined]
    deps_module._build_package_repo.cache_clear()
