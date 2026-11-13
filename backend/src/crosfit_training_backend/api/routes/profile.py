"""Authenticated athlete profile and measurement endpoints."""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from crosfit_training_backend.api.dependencies import CurrentUser
from crosfit_training_backend.api.schemas.profile import (
    AthleteProfileOut,
    AthleteProfilePatch,
    BodyMeasurementIn,
    BodyMeasurementListOut,
    BodyMeasurementOut,
)
from crosfit_training_backend.api.validation import validate_dates
from crosfit_training_backend.services import profile as services

router = APIRouter(prefix="/me", tags=["athlete profile"])


@router.get("/profile", response_model=AthleteProfileOut)
async def get_profile(user: CurrentUser) -> AthleteProfileOut:
    return await services.get_athlete_profile(user.user_id)


@router.patch("/profile", response_model=AthleteProfileOut)
async def patch_profile(
    payload: AthleteProfilePatch, user: CurrentUser
) -> AthleteProfileOut:
    return await services.patch_athlete_profile(user.user_id, payload)


@router.get("/body-measurements", response_model=BodyMeasurementListOut)
async def list_body_measurements(
    user: CurrentUser,
    date_from: Annotated[dt.date | None, Query(description="inclusive")] = None,
    date_to: Annotated[dt.date | None, Query(description="inclusive")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> BodyMeasurementListOut:
    validate_dates(date_from, date_to)
    return await services.measurements(
        user.user_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.get("/body-measurements/{measurement_date}", response_model=BodyMeasurementOut)
async def get_body_measurement(
    measurement_date: dt.date, user: CurrentUser
) -> BodyMeasurementOut:
    return await services.get_measurement(user.user_id, measurement_date)


@router.put("/body-measurements/{measurement_date}", response_model=BodyMeasurementOut)
async def put_body_measurement(
    measurement_date: dt.date, payload: BodyMeasurementIn, user: CurrentUser
) -> BodyMeasurementOut:
    """Upsert by date: one value per user/day, PUT again to edit."""
    return await services.put_measurement(user.user_id, measurement_date, payload.weight_kg)


@router.delete(
    "/body-measurements/{measurement_date}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_body_measurement(
    measurement_date: dt.date, user: CurrentUser
) -> Response:
    await services.delete_measurement(user.user_id, measurement_date)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
