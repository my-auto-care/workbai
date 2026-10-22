"""Strict, versionable schema for the provisional inspection-template document.

The final controlled inspection sheet will be approved separately. This schema is intentionally
structural: it protects item identity, option membership, and coverage without inventing field
content or vehicle-specific diagnostic policy.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_ITEM_ID = r"^[a-z][a-z0-9_-]{0,63}$"


class TemplateItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(pattern=_ITEM_ID)
    name: str = Field(min_length=1, max_length=200)
    type: Literal["condition", "measurement"] = "condition"
    unit: str | None = Field(default=None, max_length=64)
    options: list[str] | None = Field(default=None, max_length=32)

    @field_validator("options")
    @classmethod
    def valid_options(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [option.strip() for option in value]
        if not normalized or any(not option for option in normalized):
            raise ValueError("Options must be a non-empty list of non-empty labels")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Options must not contain duplicates")
        if any(len(option) > 128 for option in normalized):
            raise ValueError("Options may not exceed 128 characters")
        return normalized


class TemplateSection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(pattern=_ITEM_ID)
    name: str = Field(min_length=1, max_length=160)
    items: list[TemplateItem] = Field(min_length=1, max_length=100)


class InspectionTemplateDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version: str | int | None = None
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    sections: list[TemplateSection] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def unique_ids(self):
        section_ids = [section.id for section in self.sections]
        if len(set(section_ids)) != len(section_ids):
            raise ValueError("Section IDs must be unique")
        item_ids = [item.id for section in self.sections for item in section.items]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("Item IDs must be globally unique")
        return self

    def storage_dict(self) -> dict:
        return self.model_dump(exclude_none=True)


def validated_template_snapshot(value: object) -> dict:
    """Return a structurally safe JSON snapshot or raise Pydantic's validation error."""
    return InspectionTemplateDocument.model_validate(value).storage_dict()
