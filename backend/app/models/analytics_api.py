"""R2 本节复盘 API 模型（PRD §6.8 / API §6.1~§6.2）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SectionAnalyticsPostResponse(BaseModel):
    """POST .../analytics 200。"""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    chapter_id: int
    section_id: int
    evaluated_through_turn_id: str
    section_analytics_status: Literal["ready", "failed"]
    holistic_feedback_markdown: str
    generated_at: str

    @model_validator(mode="after")
    def markdown_by_status(self) -> SectionAnalyticsPostResponse:
        if self.section_analytics_status == "ready":
            n = len(self.holistic_feedback_markdown)
            if n < 200 or n > 20000:
                raise ValueError(f"holistic_feedback_markdown length must be 200-20000 when ready, got {n}")
        elif self.section_analytics_status == "failed":
            if self.holistic_feedback_markdown != "":
                raise ValueError("holistic_feedback_markdown must be empty when failed")
        return self


class SectionAnalyticsLatestResponse(BaseModel):
    """GET .../analytics 200（仅成功复盘）。"""

    model_config = ConfigDict(extra="forbid")

    linked_turn_id: str
    section_analytics_status: Literal["ready"]
    holistic_feedback_markdown: str = Field(min_length=200, max_length=20000)
    generated_at: str
