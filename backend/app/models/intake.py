"""五字段 intake 与扩写 analysis（API 文档 §2.5 + PRD §6.1）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class IntakeSnapshot(BaseModel):
    """已锁定的五字段快照（响应体 / intake.json）。"""

    model_config = ConfigDict(extra="forbid")

    scenario_title: str
    user_display_name: str
    scene_brief: str
    user_goal_brief: str
    vocabulary_list: str


class ScenarioAnalysis(BaseModel):
    """LLM 扩写结果（API 文档 §2.5；normalized_vocabulary 为词条数组）。"""

    model_config = ConfigDict(extra="forbid")

    enriched_scene_description: str = Field(..., min_length=200, max_length=20000)
    enriched_user_goal: str = Field(..., min_length=80, max_length=20000)
    normalized_vocabulary: list[str] = Field(
        default_factory=list,
        description="0~200 条英文词条（PRD §5.2 normalized_vocabulary）",
    )


class CommitIntakeRequest(BaseModel):
    """POST .../commit-intake 请求体（API 文档 §2.5）。

    长度下界在 Service 中按 PRD §6.1.1 校验，以便返回正确 `error_code`。
    """

    model_config = ConfigDict(extra="forbid")

    scenario_title: str = Field(..., max_length=120)
    user_display_name: str = Field(..., max_length=120)
    scene_brief: str = Field(..., max_length=20000)
    user_goal_brief: str = Field(..., max_length=20000)
    vocabulary_list: str = Field(default="", max_length=5000)
    force_reset_creation: bool = False


class CommitIntakeResponse(BaseModel):
    """POST .../commit-intake 成功响应（API 文档 §2.5）。"""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    lifecycle_phase: str
    intake_snapshot: IntakeSnapshot
    scenario_analysis: ScenarioAnalysis
    reset_applied: bool
    updated_at: str
