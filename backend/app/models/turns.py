"""单条对话回合（PRD §6.6.3）。"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import TurnWriter


class TurnRecord(BaseModel):
    """`turns.jsonl` 单行 JSON 对象。"""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1, max_length=64)
    chapter_id: int = Field(ge=1)
    section_id: int = Field(ge=1)
    turn_id: str = Field(min_length=1, max_length=64)
    created_at: str = Field(min_length=1)
    speaker_id: str = Field(min_length=1)
    recipient_id: str = Field(min_length=1)
    content: str = Field(min_length=1, max_length=8000)
    expects_user_response: bool
    turn_writer: TurnWriter

    @model_validator(mode="after")
    def cross_rules(self) -> Self:
        if self.speaker_id == self.recipient_id:
            raise ValueError("speaker_id and recipient_id must differ")
        if self.turn_writer == TurnWriter.MODEL_NPC and self.speaker_id == "user":
            raise ValueError("model_npc requires speaker_id != user")
        if self.turn_writer == TurnWriter.HUMAN_USER and self.speaker_id != "user":
            raise ValueError("human_user requires speaker_id == user")
        if self.expects_user_response and self.recipient_id != "user":
            raise ValueError("expects_user_response requires recipient_id == user")
        return self
