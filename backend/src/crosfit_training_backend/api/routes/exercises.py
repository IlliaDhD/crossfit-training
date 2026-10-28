from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Query, Response, status

from crosfit_training_backend.api.dependencies import AdminUser, CurrentUser
from crosfit_training_backend.api.schemas.exercise import (
    ExerciseIn,
    ExerciseListOut,
    ExerciseOut,
    ExerciseSearchOut,
    ExerciseUpdate,
    Modality,
    MovementPattern,
)
from crosfit_training_backend.models.exercise import Exercise
from crosfit_training_backend.services import exercises as exercise_service

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.post("", response_model=ExerciseOut, status_code=status.HTTP_201_CREATED)
async def create_exercise(payload: ExerciseIn, _: AdminUser) -> Exercise:
    return await exercise_service.create_exercise(payload)


# /search оголошений ДО /{exercise_id}, інакше "search" розбирається як id
@router.get("/search", response_model=list[ExerciseSearchOut])
async def search_exercises(
    _: CurrentUser,
    q: Annotated[str, Query(min_length=1, max_length=50, description="Prefix")],
) -> list[Exercise]:
    return await exercise_service.search_exercises(q)


@router.get("", response_model=ExerciseListOut)
async def list_exercises(
    _: CurrentUser,
    modality: Modality | None = None,
    movement_pattern: MovementPattern | None = None,
    muscle_groups: Annotated[
        list[str] | None, Query(description="Будь-яка з указаних груп м'язів")
    ] = None,
    equipment: Annotated[
        list[str] | None, Query(description="Будь-яке з указаного обладнання")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExerciseListOut:
    items, total = await exercise_service.list_exercises(
        modality=modality,
        movement_pattern=movement_pattern,
        muscle_groups=muscle_groups,
        equipment=equipment,
        limit=limit,
        offset=offset,
    )
    return ExerciseListOut(
        items=[ExerciseOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{exercise_id}", response_model=ExerciseOut)
async def get_exercise(exercise_id: PydanticObjectId, _: CurrentUser) -> Exercise:
    return await exercise_service.get_exercise(exercise_id)


@router.patch("/{exercise_id}", response_model=ExerciseOut)
async def update_exercise(
    exercise_id: PydanticObjectId, payload: ExerciseUpdate, _: AdminUser
) -> Exercise:
    return await exercise_service.update_exercise(exercise_id, payload)


@router.delete("/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_exercise(exercise_id: PydanticObjectId, _: AdminUser) -> Response:
    await exercise_service.archive_exercise(exercise_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
