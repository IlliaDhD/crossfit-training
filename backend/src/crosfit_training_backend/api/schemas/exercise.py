from typing import Annotated, Literal

from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Modality = Literal["G", "W", "M"]
MovementPattern = Literal[
    "squat", "hinge", "push", "pull", "carry", "core", "locomotion", "other"
]

Slug = Annotated[str, Field(pattern=r"^[a-z0-9-]+$", min_length=1, max_length=120)]
ExerciseName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]


class ExerciseIn(BaseModel):
    slug: Slug
    name: ExerciseName
    modality: Modality = Field(description="G - gymnastics, W - weight, M - cardio")
    movement_pattern: MovementPattern | None = None
    muscle_groups: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)


class ExerciseUpdate(BaseModel):
    """Часткове оновлення: змінюються лише передані поля. `slug` змінити не можна."""

    name: ExerciseName | None = None
    modality: Modality | None = None
    movement_pattern: MovementPattern | None = None
    muscle_groups: list[str] | None = None
    equipment: list[str] | None = None

    @model_validator(mode="after")
    def forbid_null_for_required(self):
        for field in ("name", "modality", "muscle_groups", "equipment"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId
    slug: str
    name: str
    search_terms: list[str]
    modality: Modality
    movement_pattern: MovementPattern | None
    muscle_groups: list[str]
    equipment: list[str]
    is_archived: bool


class ExerciseSearchOut(BaseModel):
    """Короткий формат для автокомпліту: modality потрібен UI для полів підходу."""

    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId
    slug: str
    name: str
    modality: Modality


class ExerciseListOut(BaseModel):
    items: list[ExerciseOut]
    total: int
    limit: int
    offset: int
