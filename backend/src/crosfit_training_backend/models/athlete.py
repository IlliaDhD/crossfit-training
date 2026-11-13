"""Athlete data stored separately from identity and workout documents."""

import datetime as dt
from typing import ClassVar
from uuid import UUID

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class AthleteProfile(Document):
    user_id: UUID
    birth_date: dt.date | None = None
    height_cm: float | None = Field(default=None, gt=0, allow_inf_nan=False)

    class Settings:
        name = "athlete_profiles"
        bson_encoders: ClassVar[dict] = {dt.date: dt.date.isoformat}
        indexes: ClassVar[list[IndexModel]] = [
            IndexModel([("user_id", ASCENDING)], unique=True, name="user_unique")
        ]


class BodyMeasurement(Document):
    user_id: UUID
    date: dt.date
    weight_kg: float = Field(gt=0, allow_inf_nan=False)

    class Settings:
        name = "body_measurements"
        bson_encoders: ClassVar[dict] = {dt.date: dt.date.isoformat}
        indexes: ClassVar[list[IndexModel]] = [
            IndexModel(
                [("user_id", ASCENDING), ("date", ASCENDING)],
                unique=True,
                name="user_date_unique",
            )
        ]
