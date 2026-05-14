"""场景包根级数据仓库。

文件结构（对齐 `01-技术方案.md` §5）：
    data/scenarios/{scenario_id}/package.json
"""

from __future__ import annotations

from pathlib import Path

from app.models.package import ScenarioPackage
from app.repositories.base import (
    read_json,
    remove_dir_tree,
    write_json_atomic,
)


class PackageRepo:
    """只负责 `package.json` 的读写与该包目录的存在性。

    业务规则（如 lifecycle 迁移合法性）由 Service 层负责，本类不感知。
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.scenarios_dir = data_dir / "scenarios"

    # === 路径辅助 ===

    def package_dir(self, scenario_id: str) -> Path:
        return self.scenarios_dir / scenario_id

    def package_path(self, scenario_id: str) -> Path:
        return self.package_dir(scenario_id) / "package.json"

    # === 单包读写 ===

    async def exists(self, scenario_id: str) -> bool:
        return self.package_path(scenario_id).exists()

    async def load(self, scenario_id: str) -> ScenarioPackage | None:
        data = await read_json(self.package_path(scenario_id))
        if data is None:
            return None
        return ScenarioPackage.model_validate(data)

    async def save(self, package: ScenarioPackage) -> None:
        await write_json_atomic(
            self.package_path(package.scenario_id),
            package.model_dump(mode="json"),
        )

    async def delete(self, scenario_id: str) -> bool:
        return await remove_dir_tree(self.package_dir(scenario_id))

    # === 全量列表 ===

    async def list_all(self) -> list[ScenarioPackage]:
        """扫描 `scenarios/` 目录，加载每个有效包；按 updated_at 降序排序。

        M1 实现：直接扫盘。当包数量增长后再考虑维护 `index.json` 索引。
        """
        if not self.scenarios_dir.exists():
            return []

        packages: list[ScenarioPackage] = []
        for entry in self.scenarios_dir.iterdir():
            if not entry.is_dir():
                continue
            pkg = await self.load(entry.name)
            if pkg is not None:
                packages.append(pkg)

        packages.sort(key=lambda p: p.updated_at, reverse=True)
        return packages

    # === 包目录下其他资产存在性查询（供 PackageSummary 的 assets 用） ===

    async def asset_exists(self, scenario_id: str, relative_path: str) -> bool:
        """检查包目录下某个相对路径文件是否存在；用于 GET /{id} 返回 assets。"""
        return (self.package_dir(scenario_id) / relative_path).exists()
