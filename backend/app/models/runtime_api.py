"""运行期 HTTP 响应模型（API 文档 §4.1 / §4.2）。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LifecyclePhase


class StoryFrameworkBriefChapter(BaseModel):
    """`story_framework_brief.chapters[]` 元素。"""

    model_config = ConfigDict(extra="forbid")

    chapter_id: int
    chapter_title: str
    section_count: int


class StoryFrameworkBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapters: list[StoryFrameworkBriefChapter]


class RuntimeResponse(BaseModel):
    """GET .../runtime 200。"""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    lifecycle_phase: LifecyclePhase
    current_chapter_id: int
    current_section_id: int
    runtime_awaiting_user: bool
    section_narrative: dict[str, Any]
    section_mission: dict[str, Any]
    character_roster: dict[str, Any]
    turns: list[dict[str, Any]]
    story_framework_brief: StoryFrameworkBrief


class EnterSectionResponse(BaseModel):
    """POST .../sections/{ch}/{sec}/enter 200。"""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    current_chapter_id: int
    current_section_id: int
    lifecycle_phase: LifecyclePhase
    runtime_awaiting_user: bool
    section_narrative: dict[str, Any]
    section_mission: dict[str, Any]
    character_roster: dict[str, Any]
    turns: list[dict[str, Any]]
    auto_opener_triggered: bool
    auto_opener_turn_id: Optional[str] = None
