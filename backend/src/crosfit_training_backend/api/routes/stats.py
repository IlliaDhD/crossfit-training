import datetime as dt
from typing import Annotated, Literal

from beanie import PydanticObjectId
from fastapi import APIRouter, Query

from crosfit_training_backend.api.dependencies import CurrentUser
from crosfit_training_backend.api.schemas.stats import (
    DistanceBest,
    RelativeStrengthPoint,
    StrengthRecord,
    TonnagePoint,
    WeeklyTonnageOut,
)
from crosfit_training_backend.api.validation import validate_dates
from crosfit_training_backend.services import stats as services
from crosfit_training_backend.services.stats import weekly_tonnage

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/weekly-tonnage", response_model=list[WeeklyTonnageOut])
async def get_weekly_tonnage(
    user: CurrentUser,
    date_from: Annotated[dt.date | None, Query(description="inclusive")] = None,
    date_to: Annotated[dt.date | None, Query(description="inclusive")] = None,
) -> list[dict]:
    """Weekly tonnage of the current user by movement pattern."""
    return await weekly_tonnage(user.user_id, date_from, date_to)


@router.get("/relative-strength", response_model=list[RelativeStrengthPoint])
async def get_relative_strength(
    user: CurrentUser,
    exercise_id: PydanticObjectId,
    reps: Annotated[int, Query(gt=0)],
    date_from: Annotated[dt.date | None, Query(description="inclusive")] = None,
    date_to: Annotated[dt.date | None, Query(description="inclusive")] = None,
) -> list[dict]:
    """Daily best W set divided by historical body weight on/before that day."""
    validate_dates(date_from, date_to)
    return await services.relative_strength(
        user.user_id,
        exercise_id=exercise_id,
        reps=reps,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/tonnage", response_model=list[TonnagePoint])
async def get_tonnage(
    user: CurrentUser,
    group_by: Literal["week", "exercise", "movement_pattern"] = "week",
    date_from: Annotated[dt.date | None, Query(description="inclusive")] = None,
    date_to: Annotated[dt.date | None, Query(description="inclusive")] = None,
) -> list[dict]:
    """Sum of W weight x reps, grouped across requested period."""
    validate_dates(date_from, date_to)
    return await services.tonnage(
        user.user_id, group_by=group_by, date_from=date_from, date_to=date_to
    )


@router.get("/strength-records", response_model=list[StrengthRecord])
async def get_strength_records(
    user: CurrentUser,
    exercise_id: PydanticObjectId | None = None,
    reps: Annotated[int | None, Query(gt=0)] = None,
    date_from: Annotated[dt.date | None, Query(description="inclusive")] = None,
    date_to: Annotated[dt.date | None, Query(description="inclusive")] = None,
) -> list[dict]:
    """All-time new maximum per exercise and exact reps, filtered after scoring."""
    validate_dates(date_from, date_to)
    return await services.strength_records(
        user.user_id,
        exercise_id=exercise_id,
        reps=reps,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/distance-bests", response_model=list[DistanceBest])
async def get_distance_bests(
    user: CurrentUser, exercise_id: PydanticObjectId | None = None
) -> list[dict]:
    """Best M time per exact (exercise_id, distance) combination."""
    return await services.distance_bests(user.user_id, exercise_id=exercise_id)
