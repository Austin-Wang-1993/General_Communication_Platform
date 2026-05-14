"""FastAPI 依赖注入工厂。

设计：
- 每个 Repo / Service 都有一个 `get_xxx()` 工厂函数；
- Router 用 `Depends(get_xxx)` 拿到实例，便于测试时 `app.dependency_overrides` 替换；
- Repo 是无状态的（只持引用到 data_dir），可缓存为单例；
- Service 也是无状态的（不持任何运行时缓存），单例缓存避免每次请求 new 对象。
"""

from __future__ import annotations

from functools import lru_cache

from app.clients.llm_client import LlmClient
from app.config import Settings, get_settings
from app.repositories.analysis_repo import AnalysisRepo
from app.repositories.intake_repo import IntakeRepo
from app.repositories.package_repo import PackageRepo
from app.services.intake_service import IntakeService
from app.services.scenario_package_service import ScenarioPackageService


# 注意：lru_cache 这里仅当 settings 不变时返回同实例；
# 测试时通过 app.dependency_overrides[get_package_repo] = lambda: PackageRepo(tmp_dir)
# 替换，本函数被绕过——所以这里缓存安全。
@lru_cache(maxsize=1)
def _build_package_repo(data_dir_str: str) -> PackageRepo:
    from pathlib import Path

    return PackageRepo(data_dir=Path(data_dir_str))


def get_package_repo(settings: Settings = None) -> PackageRepo:  # type: ignore[assignment]
    """获取 PackageRepo 单例（data_dir 来自 Settings）。"""
    if settings is None:
        settings = get_settings()
    return _build_package_repo(str(settings.data_dir_path))


def get_scenario_package_service() -> ScenarioPackageService:
    """获取 ScenarioPackageService 实例。"""
    return ScenarioPackageService(package_repo=get_package_repo())


def get_intake_service() -> IntakeService:
    """获取 IntakeService（M2：五字段 + 扩写）。"""
    pr = get_package_repo()
    settings = get_settings()
    return IntakeService(
        package_repo=pr,
        intake_repo=IntakeRepo(pr.data_dir),
        analysis_repo=AnalysisRepo(pr.data_dir),
        llm_client=LlmClient(settings),
    )
