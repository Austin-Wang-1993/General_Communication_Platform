"""场景包根级模型（对齐 PRD §5.5 + API 文档 §2 响应 schema）。

文件落盘对应 `data/scenarios/{scenario_id}/package.json`。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LifecyclePhase


class ScenarioPackage(BaseModel):
    """package.json 的领域模型。

    字段集合严格对齐 PRD §5.5，外加 `runtime_awaiting_user`（PRD §6.6 在运行期使用）。

    注：`user_display_name` 不在本模型中——它属于 §6.1 五字段 intake，
    M2 阶段会作为 `intake.json` 的字段加入。
    """

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(..., description="UUID v4；创建后不可变（PRD §5.2）")
    scenario_title: str = Field(
        default="",
        description="用户起的短标题；`draft` 阶段可为空字符串",
    )
    lifecycle_phase: LifecyclePhase = Field(..., description="生命周期阶段（PRD §5.4）")
    current_chapter_id: Optional[int] = Field(
        default=None,
        description="运行期指针所在章；仅 runtime_active 非 null（PRD §5.5）",
    )
    current_section_id: Optional[int] = Field(
        default=None,
        description="运行期指针所在节；与 current_chapter_id 同步",
    )
    runtime_awaiting_user: Optional[bool] = Field(
        default=None,
        description="运行期是否等待用户发言；非运行期为 null",
    )
    created_at: str = Field(..., description="RFC 3339 / ISO 8601 UTC（PRD §5.3）")
    updated_at: str = Field(..., description="RFC 3339 / ISO 8601 UTC")


# === API 响应专用 schema ===


class PackageListItem(BaseModel):
    """GET /api/v1/scenario-packages 列表项（API 文档 §2.2）。"""

    scenario_id: str
    scenario_title: str
    lifecycle_phase: LifecyclePhase
    current_chapter_id: Optional[int] = None
    current_section_id: Optional[int] = None
    created_at: str
    updated_at: str


class PackageListResponse(BaseModel):
    """GET /api/v1/scenario-packages 响应（API 文档 §2.2）。"""

    packages: list[PackageListItem]


class PackageAssets(BaseModel):
    """GET /api/v1/scenario-packages/{id} 中的 assets 概览（API 文档 §2.3）。

    M1：所有 has_* 默认为 False，section_assets_count 为 0；
    M2+ 每实现一个智能体就把对应字段填上。
    """

    has_intake_snapshot: bool = False
    has_scenario_analysis: bool = False
    has_story_framework: bool = False
    has_character_roster: bool = False
    section_assets_count: int = 0
    section_assets_complete: bool = False


class PackageSummary(BaseModel):
    """GET /api/v1/scenario-packages/{id} 完整响应（API 文档 §2.3）。"""

    scenario_id: str
    scenario_title: str
    lifecycle_phase: LifecyclePhase
    current_chapter_id: Optional[int] = None
    current_section_id: Optional[int] = None
    runtime_awaiting_user: Optional[bool] = None
    created_at: str
    updated_at: str
    assets: PackageAssets


class CreatePackageRequest(BaseModel):
    """POST /api/v1/scenario-packages 请求体（API 文档 §2.1）。"""

    model_config = ConfigDict(extra="forbid")

    scenario_title_hint: str = Field(
        default="",
        max_length=120,
        description="可选；后续 P2.1 表单的默认填充值；不参与机读语义",
    )


class CreatePackageResponse(BaseModel):
    """POST /api/v1/scenario-packages 响应（API 文档 §2.1）。"""

    scenario_id: str
    lifecycle_phase: LifecyclePhase
    scenario_title: str
    created_at: str
    updated_at: str
