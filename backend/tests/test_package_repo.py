"""PackageRepo 单元测试（M1）。

只测数据存取，不涉及业务规则。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.enums import LifecyclePhase
from app.models.package import ScenarioPackage
from app.repositories.package_repo import PackageRepo


def _make_pkg(scenario_id: str = "test-id", *, updated_at: str = "2026-01-01T00:00:00Z") -> ScenarioPackage:
    return ScenarioPackage(
        scenario_id=scenario_id,
        scenario_title="测试包",
        lifecycle_phase=LifecyclePhase.DRAFT,
        created_at="2026-01-01T00:00:00Z",
        updated_at=updated_at,
    )


@pytest.mark.asyncio
async def test_save_and_load_round_trip(tmp_path: Path) -> None:
    repo = PackageRepo(data_dir=tmp_path)
    pkg = _make_pkg("aaa-111")

    await repo.save(pkg)
    loaded = await repo.load("aaa-111")

    assert loaded is not None
    assert loaded.scenario_id == "aaa-111"
    assert loaded.scenario_title == "测试包"
    assert loaded.lifecycle_phase == LifecyclePhase.DRAFT


@pytest.mark.asyncio
async def test_load_nonexistent_returns_none(tmp_path: Path) -> None:
    repo = PackageRepo(data_dir=tmp_path)
    assert await repo.load("not-exist") is None
    assert await repo.exists("not-exist") is False


@pytest.mark.asyncio
async def test_delete_removes_entire_package_dir(tmp_path: Path) -> None:
    repo = PackageRepo(data_dir=tmp_path)
    pkg = _make_pkg("to-delete")
    await repo.save(pkg)
    assert await repo.exists("to-delete")

    # 在包目录里放点其他文件，确认递归清除
    (repo.package_dir("to-delete") / "intake.json").write_text("{}")
    (repo.package_dir("to-delete") / "sections").mkdir()

    ok = await repo.delete("to-delete")
    assert ok is True
    assert not repo.package_dir("to-delete").exists()


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_false(tmp_path: Path) -> None:
    repo = PackageRepo(data_dir=tmp_path)
    assert await repo.delete("no-such") is False


@pytest.mark.asyncio
async def test_list_all_sorted_by_updated_at_desc(tmp_path: Path) -> None:
    repo = PackageRepo(data_dir=tmp_path)
    await repo.save(_make_pkg("a", updated_at="2026-01-01T00:00:00Z"))
    await repo.save(_make_pkg("b", updated_at="2026-01-03T00:00:00Z"))
    await repo.save(_make_pkg("c", updated_at="2026-01-02T00:00:00Z"))

    packages = await repo.list_all()
    ids = [p.scenario_id for p in packages]
    assert ids == ["b", "c", "a"]


@pytest.mark.asyncio
async def test_list_all_empty_when_no_dir(tmp_path: Path) -> None:
    # 不预先创建 scenarios/ 目录
    repo = PackageRepo(data_dir=tmp_path)
    assert await repo.list_all() == []


@pytest.mark.asyncio
async def test_asset_exists_probe(tmp_path: Path) -> None:
    repo = PackageRepo(data_dir=tmp_path)
    await repo.save(_make_pkg("p"))

    assert await repo.asset_exists("p", "intake.json") is False
    (repo.package_dir("p") / "intake.json").write_text("{}")
    assert await repo.asset_exists("p", "intake.json") is True


@pytest.mark.asyncio
async def test_atomic_write_no_partial_file(tmp_path: Path) -> None:
    """落盘失败时不留半截文件——通过观察 .tmp 在写后被清理验证。"""
    repo = PackageRepo(data_dir=tmp_path)
    pkg = _make_pkg("xy")
    await repo.save(pkg)

    pkg_path = repo.package_path("xy")
    assert pkg_path.exists()
    # 同目录内不应残留 .tmp
    assert not pkg_path.with_suffix(pkg_path.suffix + ".tmp").exists()
