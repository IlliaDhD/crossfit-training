"""Sections and trainings (data-model.md, sections 6, 8, 9.4, 9.5)."""

import datetime as dt
from typing import Annotated, Literal
from uuid import UUID

from beanie import PydanticObjectId
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from crosfit_training_backend.api.schemas.sets import SectionItemIn, SetDB

SectionKind = Literal["warm_up", "lifting", "metcon", "accessory", "cool_down"]
SectionFormat = Literal["standard", "amrap", "emom", "for_time", "tabata"]

SCHEMA_VERSION = 1


def _as_utc(value: dt.datetime) -> dt.datetime:
    # MongoDB returns naive datetimes (always UTC); the API must say so explicitly
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.UTC)
    return value.astimezone(dt.UTC)


UtcDatetime = Annotated[dt.datetime, AfterValidator(_as_utc)]


# ------------------------------------------------------------ input (9.4)


class SectionIn(BaseModel):
    kind: SectionKind
    format: SectionFormat = "standard"
    rounds: int | None = Field(None, gt=0)
    time_cap: int | None = Field(None, gt=0, description="seconds")
    items: list[SectionItemIn] = Field(min_length=1)
    comment: str | None = None

    @model_validator(mode="after")
    def check_format(self):
        if self.format in ("amrap", "emom") and not self.time_cap:
            raise ValueError(f"{self.format} requires time_cap")
        if self.format == "for_time" and not self.rounds:
            raise ValueError("for_time requires rounds")
        return self


class TrainingIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    date: dt.date = Field(description="YYYY-MM-DD, no time, no time zone")
    comment: str | None = None
    sections: list[SectionIn] = Field(min_length=1)

    def exercise_ids(self) -> set[PydanticObjectId]:
        """Exercises referenced directly by sets (not those inside complexes)."""
        return {
            i.exercise_id for s in self.sections for i in s.items if i.type != "complex"
        }

    def complex_ids(self) -> set[PydanticObjectId]:
        return {
            i.complex_id for s in self.sections for i in s.items if i.type == "complex"
        }


# ------------------------------------------------------------ stored (9.5)


class SectionDB(SectionIn):
    """References are already expanded, so `items` contain only sets."""

    items: list[SetDB]  # type: ignore[assignment]


class TrainingDB(TrainingIn):
    schema_version: int = SCHEMA_VERSION
    user_id: UUID
    created_by: UUID
    created_at: UtcDatetime
    updated_at: UtcDatetime
    sections: list[SectionDB]  # type: ignore[assignment]


class TrainingOut(TrainingDB):
    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId


class TrainingListOut(BaseModel):
    items: list[TrainingOut]
    total: int
    limit: int
    offset: int
