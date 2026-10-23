import datetime as dt
from typing import Any, ClassVar

from beanie import Document
from pymongo import ASCENDING, DESCENDING, IndexModel

from crosfit_training_backend.api.schemas.training import TrainingDB


def _encode_date(value: dt.date) -> Any:
    # `date` is stored as an ISO string `YYYY-MM-DD` (data-model.md, section 2), so
    # range queries ($gte, $lt) work without time zone handling. Beanie matches
    # custom encoders with isinstance, and datetime is a subclass of date, so
    # datetimes (created_at, updated_at) must be passed through untouched.
    if isinstance(value, dt.datetime):
        return value
    return value.isoformat()


class Training(Document, TrainingDB):
    """Workout log. The set structure and validation live in `TrainingDB`."""

    class Settings:
        name = "trainings"
        bson_encoders: ClassVar[dict] = {dt.date: _encode_date}
        indexes: ClassVar[list[IndexModel]] = [
            IndexModel(
                [("user_id", ASCENDING), ("date", DESCENDING)],
                name="user_date",
            ),
            IndexModel(
                [("user_id", ASCENDING), ("sections.items.exercise_id", ASCENDING)],
                name="user_exercise",
            ),
            IndexModel(
                [("sections.items.complex.id", ASCENDING)],
                name="complex_id",
            ),
        ]
