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


class PostUserTurnRequest(BaseModel):
    """POST .../sections/{ch}/{sec}/turns 请求体（API §4.5）。"""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(default="", max_length=8000)
    recipient_id: str = Field(min_length=1, max_length=64)


class PostUserTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_turns: list[dict[str, Any]]
    runtime_awaiting_user: bool


class SectionTurnsListResponse(BaseModel):
    """GET .../sections/{ch}/{sec}/turns 200（API §4.4）。"""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    chapter_id: int
    section_id: int
    turns: list[dict[str, Any]]


class AutoOpenerRetryResponse(BaseModel):
    """POST .../auto-opener 200（API §4.3）。"""

    model_config = ConfigDict(extra="forbid")

    turn: dict[str, Any]
    turns: list[dict[str, Any]]
    runtime_awaiting_user: bool


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
