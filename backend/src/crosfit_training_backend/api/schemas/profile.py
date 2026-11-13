"""Public contracts for the athlete profile and training statistics API."""

import datetime as dt

from pydantic import BaseModel, Field, field_validator


class AthleteProfilePatch(BaseModel):
    """Omitted properties remain unchanged; explicit null removes the value."""

    birth_date: dt.date | None = None
    height_cm: float | None = Field(default=None, gt=0, allow_inf_nan=False)

    @field_validator("birth_date")
    @classmethod
    def birth_date_cannot_be_in_future(cls, value: dt.date | None) -> dt.date | None:
        if value is not None and value > dt.date.today():
            raise ValueError("birth_date must not be in the future")
        return value


class AthleteProfileOut(BaseModel):
    birth_date: dt.date | None = None
    height_cm: float | None = None
    current_weight_kg: float | None = None
    current_weight_date: dt.date | None = None


class BodyMeasurementIn(BaseModel):
    weight_kg: float = Field(gt=0, allow_inf_nan=False)


class BodyMeasurementOut(BodyMeasurementIn):
    date: dt.date


class BodyMeasurementListOut(BaseModel):
    items: list[BodyMeasurementOut]
    total: int
    limit: int
    offset: int
