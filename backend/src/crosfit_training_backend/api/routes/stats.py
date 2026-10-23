import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query

from crosfit_training_backend.api.dependencies import CurrentUser
from crosfit_training_backend.api.schemas.stats import WeeklyTonnageOut
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
