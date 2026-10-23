"""Sets (data-model.md, sections 5, 7.2, 9.3, 9.3.1, 9.5).

`type` (the exercise modality) is the discriminator: it selects the set model.
Units are fixed by the data model and repeated in the field descriptions, so they
appear in the OpenAPI spec: time - seconds, distance - meters, weight - kilograms.
"""

from typing import Annotated, Literal

from beanie import PydanticObjectId
from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------- input (9.3)


class SetBase(BaseModel):
    exercise_id: PydanticObjectId
    comment: str | None = None


class GymSetIn(SetBase):
    type: Literal["G"]
    reps: int = Field(gt=0)
    time: int | None = Field(None, gt=0, description="seconds")
    weight: float | None = Field(None, gt=0, description="kilograms")


class WeightSetIn(SetBase):
    type: Literal["W"]
    reps: int = Field(gt=0)
    weight: float | None = Field(None, gt=0, description="kilograms")
    rpe: float | None = Field(None, ge=1, le=10)
    time: int | None = Field(None, gt=0, description="seconds")


class CardioSetIn(SetBase):
    type: Literal["M"]
    time: int | None = Field(None, gt=0, description="seconds")
    calories: int | None = Field(None, gt=0, description="kcal")
    distance: int | None = Field(None, gt=0, description="meters")

    @model_validator(mode="after")
    def at_least_one_metric(self):
        if not (self.time or self.calories or self.distance):
            raise ValueError("At least one of time, calories, distance is required")
        return self


SetIn = Annotated[
    GymSetIn | WeightSetIn | CardioSetIn,
    Field(discriminator="type"),
]


# ------------------------------------------------------ complex reference (9.3.1)


class ComplexRefIn(BaseModel):
    """Reference to a complex template; expanded into plain sets on save."""

    type: Literal["complex"]
    complex_id: PydanticObjectId
    rounds: int = Field(1, gt=0, description="how many times the complex was performed")
    weight: float | None = Field(
        None,
        gt=0,
        description="kilograms; shared weight for W and G components without own weight",
    )
    rpe: float | None = Field(
        None, ge=1, le=10, description="applied to W components without own rpe"
    )


SectionItemIn = Annotated[
    GymSetIn | WeightSetIn | CardioSetIn | ComplexRefIn,
    Field(discriminator="type"),
]


# ------------------------------------------------------------ stored (9.5)


class ExerciseSnapshot(BaseModel):
    """Copy of the exercise data kept inside every saved set (principle 4)."""

    name: str
    movement_pattern: str | None = None
    muscle_groups: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)


class ComplexMarker(BaseModel):
    """Marks a set that came from an expanded complex. UI groups by `id` + `round`."""

    id: PydanticObjectId
    name: str
    round: int = Field(ge=1)


class _DBMixin(BaseModel):
    exercise: ExerciseSnapshot
    complex: ComplexMarker | None = None


class GymSetDB(GymSetIn, _DBMixin): ...


class WeightSetDB(WeightSetIn, _DBMixin): ...


class CardioSetDB(CardioSetIn, _DBMixin): ...


SetDB = Annotated[
    GymSetDB | WeightSetDB | CardioSetDB,
    Field(discriminator="type"),
]

# set type -> stored model; used by `build_training_doc`
SET_DB_MODELS: dict[str, type[GymSetDB | WeightSetDB | CardioSetDB]] = {
    "G": GymSetDB,
    "W": WeightSetDB,
    "M": CardioSetDB,
}
