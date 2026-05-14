"""§6.4 / §6.5 小节落盘 JSON 校验（PRD）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SectionNarrativePayload(BaseModel):
    """与 `sections/ch*_sec*/narrative.json` 内容一致。"""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1, max_length=64)
    chapter_id: int = Field(ge=1)
    section_id: int = Field(ge=1)
    section_body: str = Field(min_length=300, max_length=20000)
    appearing_npc_ids: list[str] = Field(min_length=1, max_length=2)

    @field_validator("appearing_npc_ids")
    @classmethod
    def npc_ids_nonempty_strings(cls, v: list[str]) -> list[str]:
        for x in v:
            if not x or x.strip() != x or x == "user":
                raise ValueError("appearing_npc_ids must be non-empty npc ids, never user")
        if len(set(v)) != len(v):
            raise ValueError("duplicate appearing_npc_ids")
        return v


class SectionMissionPayload(BaseModel):
    """与 `sections/ch*_sec*/mission.json` 内容一致。"""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1, max_length=64)
    chapter_id: int = Field(ge=1)
    section_id: int = Field(ge=1)
    section_objective: str = Field(min_length=40, max_length=1200)
