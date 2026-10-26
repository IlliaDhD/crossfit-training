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
from crosfit_training_backend.api.schemas.user import AuthUser
from crosfit_training_backend.exceptions import ForbiddenError, NotFoundError
from crosfit_training_backend.models.training import Training
from crosfit_training_backend.services.trainings import build_training_doc

router = APIRouter(prefix="/trainings", tags=["trainings"])


async def _get_own_or_error(training_id: PydanticObjectId, user: AuthUser) -> Training:
    """404 for a missing training, 403 for someone else's (data-model.md, 13)."""
    training = await Training.get(training_id)
    if training is None:
        raise NotFoundError("Training not found")
    if training.user_id != user.user_id:
        raise ForbiddenError()
    return training


@router.post("", response_model=TrainingOut, status_code=status.HTTP_201_CREATED)
async def create_training(payload: TrainingIn, user: CurrentUser) -> Training:
    """Save a logged workout. Complex references are expanded into plain sets and
    every set gets an exercise snapshot."""
    built = await build_training_doc(
        payload, user_id=user.user_id, created_by=user.user_id
    )
    training = Training(**built.model_dump())
    await training.insert()
    return training


@router.get("", response_model=TrainingListOut)
async def list_trainings(
    user: CurrentUser,
    date_from: Annotated[dt.date | None, Query(description="inclusive")] = None,
    date_to: Annotated[dt.date | None, Query(description="inclusive")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TrainingListOut:
    """Own trainings, newest first. Used by the calendar and list views."""
    query: dict = {"user_id": user.user_id}
    date_range: dict = {}
    if date_from:
        date_range["$gte"] = date_from.isoformat()
    if date_to:
        date_range["$lte"] = date_to.isoformat()
    if date_range:
        # `date` is an ISO string: string comparison equals date comparison
        query["date"] = date_range

    found = Training.find(query)
    total = await found.count()
    items = (
        await found.sort([("date", -1), ("created_at", -1)])
        .skip(offset)
        .limit(limit)
        .to_list()
    )
    return TrainingListOut(
        items=[TrainingOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{training_id}", response_model=TrainingOut)
async def get_training(training_id: PydanticObjectId, user: CurrentUser) -> Training:
    return await _get_own_or_error(training_id, user)


@router.put("/{training_id}", response_model=TrainingOut)
async def replace_training(
    training_id: PydanticObjectId, payload: TrainingIn, user: CurrentUser
) -> Training:
    """Replace the whole training. The document is rebuilt from the payload;
    expanded sets are never patched by hand (data-model.md, 7.3)."""
    training = await _get_own_or_error(training_id, user)
    built = await build_training_doc(
        payload,
        user_id=training.user_id,
        created_by=training.created_by,
        created_at=training.created_at,
    )
    training.schema_version = built.schema_version
    training.title = built.title
    training.date = built.date
    training.comment = built.comment
    training.sections = built.sections
    training.updated_at = built.updated_at
    await training.save()
    return training


@router.delete("/{training_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_training(training_id: PydanticObjectId, user: CurrentUser) -> Response:
    training = await _get_own_or_error(training_id, user)
    await training.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
