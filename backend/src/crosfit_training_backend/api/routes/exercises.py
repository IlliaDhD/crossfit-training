import re
from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query, Response, status
from pymongo.errors import DuplicateKeyError

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
from crosfit_training_backend.exceptions import NotFoundError
from crosfit_training_backend.models.exercise import Exercise
from crosfit_training_backend.services.exercises import (
    build_search_terms,
    exercise_is_used,
)

router = APIRouter(prefix="/exercises", tags=["exercises"])

SEARCH_LIMIT = 10


async def _get_or_404(exercise_id: PydanticObjectId) -> Exercise:
    exercise = await Exercise.get(exercise_id)
    if exercise is None:
        raise NotFoundError("Exercise not found")
    return exercise


@router.post("", response_model=ExerciseOut, status_code=status.HTTP_201_CREATED)
async def create_exercise(payload: ExerciseIn, _: AdminUser) -> Exercise:
    exercise = Exercise(
        **payload.model_dump(), search_terms=build_search_terms(payload.name)
    )
    try:
        await exercise.insert()
    except DuplicateKeyError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Exercise with this slug already exists"
        ) from None
    return exercise


# /search оголошений ДО /{exercise_id}, інакше "search" розбирається як id
@router.get("/search", response_model=list[ExerciseSearchOut])
async def search_exercises(
    _: CurrentUser,
    q: Annotated[str, Query(min_length=1, max_length=50, description="Prefix")],
) -> list[Exercise]:
    prefix = q.strip().lower()
    if not prefix:
        return []
    return (
        await Exercise.find(
            {
                "is_archived": False,
                "search_terms": {"$regex": f"^{re.escape(prefix)}"},
            }
        )
        .sort("name")
        .limit(SEARCH_LIMIT)
        .to_list()
    )


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
    query: dict = {"is_archived": False}
    if modality:
        query["modality"] = modality
    if movement_pattern:
        query["movement_pattern"] = movement_pattern
    if muscle_groups:
        query["muscle_groups"] = {"$in": muscle_groups}
    if equipment:
        query["equipment"] = {"$in": equipment}

    found = Exercise.find(query)
    total = await found.count()
    items = await found.sort("name").skip(offset).limit(limit).to_list()
    return ExerciseListOut(
        items=[ExerciseOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{exercise_id}", response_model=ExerciseOut)
async def get_exercise(exercise_id: PydanticObjectId, _: CurrentUser) -> Exercise:
    # заархівовані теж повертаються: старі тренування посилаються на них
    return await _get_or_404(exercise_id)


@router.patch("/{exercise_id}", response_model=ExerciseOut)
async def update_exercise(
    exercise_id: PydanticObjectId, payload: ExerciseUpdate, _: AdminUser
) -> Exercise:
    exercise = await _get_or_404(exercise_id)
    changes = payload.model_dump(exclude_unset=True)

    new_modality = changes.get("modality")
    if (
        new_modality is not None
        and new_modality != exercise.modality
        and await exercise_is_used(exercise_id)
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Modality cannot be changed: exercise is used in a training",
        )

    for field, value in changes.items():
        setattr(exercise, field, value)
    if "name" in changes:
        exercise.search_terms = build_search_terms(exercise.name)

    await exercise.save()
    return exercise


@router.delete("/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_exercise(exercise_id: PydanticObjectId, _: AdminUser) -> Response:
    exercise = await _get_or_404(exercise_id)
    if not exercise.is_archived:
        exercise.is_archived = True
        await exercise.save()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
