from typing import ClassVar

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from crosfit_training_backend.api.schemas.exercise_catalog import (
    ExerciseName,
    Modality,
    MovementPattern,
    Slug,
)


class Exercise(Document):
    slug: Slug
    name: ExerciseName
    search_terms: list[str]
    modality: Modality
    movement_pattern: MovementPattern | None = None
    muscle_groups: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    is_archived: bool = False

    class Settings:
        name = "exercises"
        indexes: ClassVar[list[IndexModel]] = [
            IndexModel([("slug", ASCENDING)], name="slug_unique", unique=True),
            IndexModel([("search_terms", ASCENDING)], name="search_terms"),
        ]
