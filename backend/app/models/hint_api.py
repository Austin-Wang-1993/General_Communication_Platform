"""R1 回答提示 API 模型（PRD §6.7 / API §5.1~§5.2）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PostHintRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_turn_id: str = Field(min_length=1, max_length=64)


class HintResponse(BaseModel):
    """POST hints 200 / GET hints/latest 200（hint_status=ready 或 stale）。"""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    chapter_id: int
    section_id: int
    linked_turn_id: str
    hint_status: Literal["ready", "stale", "failed"]
    analysis_markdown: str
    suggested_utterances: list[str] = Field(default_factory=list)
    generated_at: str

    @field_validator("suggested_utterances")
    @classmethod
    def utterances_strings(cls, v: list[str]) -> list[str]:
        return [str(x) for x in v]

    @model_validator(mode="after")
    def lengths_by_status(self) -> HintResponse:
        if self.hint_status == "ready":
            al = len(self.analysis_markdown)
            if al < 40 or al > 12000:
                raise ValueError(f"analysis_markdown length must be 40-12000 when ready, got {al}")
            n = len(self.suggested_utterances)
            if not (1 <= n <= 5):
                raise ValueError("suggested_utterances must have 1-5 items when ready")
            for i, u in enumerate(self.suggested_utterances):
                ul = len(u)
                if ul < 10 or ul > 400:
                    raise ValueError(f"suggested_utterances[{i}] length must be 10-400, got {ul}")
        elif self.hint_status == "stale":
            if self.analysis_markdown != "":
                raise ValueError("analysis_markdown must be empty when stale")
            if self.suggested_utterances:
                raise ValueError("suggested_utterances must be empty when stale")
        return self
