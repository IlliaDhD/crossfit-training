import datetime as dt
from typing import Literal

from beanie import PydanticObjectId
from pydantic import BaseModel, Field


class WeeklyTonnageOut(BaseModel):
    year: int = Field(description="ISO week-numbering year")
    week: int = Field(description="ISO week number")
    movement_pattern: str | None
    tonnage: float = Field(description="sum of reps * weight, kilograms")
    sets: int


class RelativeStrengthPoint(BaseModel):
    date: dt.date
    exercise_id: PydanticObjectId
    exercise_name: str
    reps: int
    weight_kg: float
    body_weight_kg: float | None
    measurement_date: dt.date | None
    relative_strength: float | None = Field(description="weight_kg / body_weight_kg")
    status: Literal["ok", "insufficient_data"]
    training_id: PydanticObjectId


class TonnagePoint(BaseModel):
    group_by: Literal["week", "exercise", "movement_pattern"]
    tonnage: float = Field(description="Sum of W set weight * reps, in kilograms")
    sets: int
    year: int | None = None
    week: int | None = None
    exercise_id: PydanticObjectId | None = None
    exercise_name: str | None = None
    movement_pattern: str | None = None


class StrengthRecord(BaseModel):
    date: dt.date
    exercise_id: PydanticObjectId
    exercise_name: str
    reps: int
    weight_kg: float
    improvement_kg: float | None = Field(
        description="Increase over previous record, null for the first record"
    )
    training_id: PydanticObjectId


class DistanceBest(BaseModel):
    exercise_id: PydanticObjectId
    exercise_name: str
    distance: int = Field(description="meters")
    time_seconds: int
    date: dt.date
    training_id: PydanticObjectId
