"""场景包包级业务服务（M1：CRUD）。

对齐：
- PRD §5.4 / §5.5 包级语义
- 业务流程 §2.2 状态迁移表（M1 涉及：〈不存在〉→draft、任意状态→〈不存在〉）
- API 文档 §2.1 ~ §2.4

M2+ 会扩展 `commit_intake` 等业务方法。
"""

from __future__ import annotations

from app.errors import ScenarioNotFoundError
from app.lib.clock import utc_now_rfc3339
from app.lib.ids import new_scenario_id
from app.models.enums import LifecyclePhase
from app.models.package import (
    PackageAssets,
    PackageListItem,
    PackageSummary,
    ScenarioPackage,
)
from app.models.story_assets import StoryFrameworkFile
from app.repositories.base import get_scenario_lock, read_json, release_scenario_lock
from app.repositories.package_repo import PackageRepo


class ScenarioPackageService:
    """场景包根级业务服务。

    构造时注入 Repo（依赖注入，便于测试时替换数据目录）。
    """

    def __init__(self, package_repo: PackageRepo) -> None:
        self.repo = package_repo

    # === POST /scenario-packages：创建空 draft 包 ===

    async def create_empty(self, scenario_title_hint: str = "") -> ScenarioPackage:
        scenario_id = new_scenario_id()
        now = utc_now_rfc3339()
        package = ScenarioPackage(
            scenario_id=scenario_id,
            scenario_title=scenario_title_hint.strip(),
            lifecycle_phase=LifecyclePhase.DRAFT,
            current_chapter_id=None,
            current_section_id=None,
            runtime_awaiting_user=None,
            created_at=now,
            updated_at=now,
        )
        async with get_scenario_lock(scenario_id):
            await self.repo.save(package)
        return package

    # === GET /scenario-packages：列表 ===

    async def list_all(self) -> list[PackageListItem]:
        packages = await self.repo.list_all()
        return [
            PackageListItem(
                scenario_id=p.scenario_id,
                scenario_title=p.scenario_title,
                lifecycle_phase=p.lifecycle_phase,
                current_chapter_id=p.current_chapter_id,
                current_section_id=p.current_section_id,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in packages
        ]

    # === GET /scenario-packages/{id}：完整摘要 ===

    async def get_summary(self, scenario_id: str) -> PackageSummary:
        async with get_scenario_lock(scenario_id):
            pkg = await self.repo.load(scenario_id)
            if pkg is None:
                raise ScenarioNotFoundError(details={"scenario_id": scenario_id})
            assets = await self._compute_assets(scenario_id)

        return PackageSummary(
            scenario_id=pkg.scenario_id,
            scenario_title=pkg.scenario_title,
            lifecycle_phase=pkg.lifecycle_phase,
            current_chapter_id=pkg.current_chapter_id,
            current_section_id=pkg.current_section_id,
            runtime_awaiting_user=pkg.runtime_awaiting_user,
            created_at=pkg.created_at,
            updated_at=pkg.updated_at,
            assets=assets,
        )

    async def _compute_assets(self, scenario_id: str) -> PackageAssets:
        """探测包目录下各产物文件的存在性。

        M2：`has_intake_snapshot` / `has_scenario_analysis` 在 commit-intake 后为 True。
        M3：`has_story_framework` / `has_character_roster` 在 framework Job 成功后为 True。
        M4：按 framework 小节数统计已落盘 narrative+mission 的节数。
        """
        section_count, section_complete = await self._section_asset_status(scenario_id)
        return PackageAssets(
            has_intake_snapshot=await self.repo.asset_exists(scenario_id, "intake.json"),
            has_scenario_analysis=await self.repo.asset_exists(scenario_id, "analysis.json"),
            has_story_framework=await self.repo.asset_exists(scenario_id, "framework.json"),
            has_character_roster=await self.repo.asset_exists(scenario_id, "roster.json"),
            section_assets_count=section_count,
            section_assets_complete=section_complete,
        )

    async def _section_asset_status(self, scenario_id: str) -> tuple[int, bool]:
        fw_path = self.repo.package_dir(scenario_id) / "framework.json"
        raw = await read_json(fw_path)
        if not isinstance(raw, dict):
            return 0, False
        try:
            sf = StoryFrameworkFile.model_validate(raw)
        except Exception:
            return 0, False
        root = self.repo.package_dir(scenario_id) / "sections"
        total = sum(len(ch.sections) for ch in sf.story_framework.chapters)
        if total == 0:
            return 0, False
        done = 0
        for ch in sf.story_framework.chapters:
            for sec in ch.sections:
                d = root / f"ch{ch.chapter_id}_sec{sec.section_id}"
                if (d / "narrative.json").exists() and (d / "mission.json").exists():
                    done += 1
        return done, done == total

    # === DELETE /scenario-packages/{id}：物理删除 ===

    async def delete(self, scenario_id: str) -> None:
        async with get_scenario_lock(scenario_id):
            ok = await self.repo.delete(scenario_id)
        if not ok:
            raise ScenarioNotFoundError(details={"scenario_id": scenario_id})
        # 包已删除，释放对应锁条目避免内存累积
        release_scenario_lock(scenario_id)
