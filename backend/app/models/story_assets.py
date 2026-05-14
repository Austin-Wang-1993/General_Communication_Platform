"""§6.2 / §6.3 落盘 JSON 的 Pydantic 校验（PRD 结构硬约束子集）。"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrameworkSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: int = Field(ge=1, le=100)
    section_title: str = Field(min_length=1, max_length=120)
    section_summary: str = Field(min_length=20, max_length=800)


class FrameworkChapter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: int = Field(ge=1, le=20)
    chapter_title: str = Field(min_length=1, max_length=120)
    chapter_summary: str = Field(min_length=40, max_length=2000)
    sections: list[FrameworkSection] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def section_ids_strict(self) -> Self:
        ids = [s.section_id for s in self.sections]
        if len(set(ids)) != len(ids):
            raise ValueError("section_id must be unique within chapter")
        if ids != sorted(ids):
            raise ValueError("section_id must be strictly increasing")
        return self


class StoryFrameworkPayload(BaseModel):
    """`story_framework` 对象本体（不含外层键名）。"""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=36, max_length=36)
    chapters: list[FrameworkChapter] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_book_shape(self) -> Self:
        cids = [c.chapter_id for c in self.chapters]
        if len(set(cids)) != len(cids):
            raise ValueError("chapter_id must be unique")
        if cids != sorted(cids):
            raise ValueError("chapter_id must be strictly increasing")
        total = sum(len(c.sections) for c in self.chapters)
        if not 1 <= total <= 20:
            raise ValueError("total sections K must be between 1 and 20")
        return self


class StoryFrameworkFile(BaseModel):
    """磁盘 `framework.json` 根结构。"""

    model_config = ConfigDict(extra="forbid")

    story_framework: StoryFrameworkPayload


class CharacterEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=4, max_length=200)
    personality: str = Field(min_length=20, max_length=800)
    is_user: bool


class CharacterRosterPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=36, max_length=36)
    characters: list[CharacterEntry] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def exactly_one_user(self) -> Self:
        users = [c for c in self.characters if c.is_user]
        if len(users) != 1:
            raise ValueError("exactly one character must have is_user true")
        if users[0].character_id != "user":
            raise ValueError("user entry must have character_id 'user'")
        npc_ids = [c.character_id for c in self.characters if not c.is_user]
        if len(set(npc_ids)) != len(npc_ids):
            raise ValueError("duplicate npc character_id")
        return self


class CharacterRosterFile(BaseModel):
    """磁盘 `roster.json` 根结构。"""

    model_config = ConfigDict(extra="forbid")

    character_roster: CharacterRosterPayload
