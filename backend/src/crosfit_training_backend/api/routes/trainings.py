import datetime as dt
from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Query, Response, status

from crosfit_training_backend.api.dependencies import CurrentUser
from crosfit_training_backend.api.schemas.training import (
    TrainingIn,
    TrainingListOut,
    TrainingOut,
)
from crosfit_training_backend.models.training import Training
from crosfit_training_backend.services import trainings as training_service

router = APIRouter(prefix="/trainings", tags=["trainings"])


@router.post("", response_model=TrainingOut, status_code=status.HTTP_201_CREATED)
async def create_training(payload: TrainingIn, user: CurrentUser) -> Training:
    """Save a logged workout. Complex references are expanded into plain sets and
    every set gets an exercise snapshot."""
    return await training_service.create_training(payload, user.user_id)


@router.get("", response_model=TrainingListOut)
async def list_trainings(
    user: CurrentUser,
    date_from: Annotated[dt.date | None, Query(description="inclusive")] = None,
    date_to: Annotated[dt.date | None, Query(description="inclusive")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TrainingListOut:
    """Own trainings, newest first. Used by the calendar and list views."""
    items, total = await training_service.list_trainings(
        user.user_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return TrainingListOut(
        items=[TrainingOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{training_id}", response_model=TrainingOut)
async def get_training(training_id: PydanticObjectId, user: CurrentUser) -> Training:
    return await training_service.get_own_training(training_id, user.user_id)


@router.put("/{training_id}", response_model=TrainingOut)
async def replace_training(
    training_id: PydanticObjectId, payload: TrainingIn, user: CurrentUser
) -> Training:
    """Replace the whole training; the document is rebuilt from the payload."""
    return await training_service.replace_training(training_id, payload, user.user_id)


@router.delete("/{training_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_training(training_id: PydanticObjectId, user: CurrentUser) -> Response:
    await training_service.delete_training(training_id, user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
