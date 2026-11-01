import re

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from crosfit_training_backend.api.schemas.exercise import (
    ExerciseIn,
    ExerciseUpdate,
    Modality,
    MovementPattern,
)
from crosfit_training_backend.exceptions import ConflictError, NotFoundError
from crosfit_training_backend.models.exercise import Exercise

SEARCH_LIMIT = 10


def build_search_terms(name: str) -> list[str]:
    """Повна назва в нижньому регістрі + кожне слово назви (без дублікатів)."""
    n = name.lower().strip()
    return list(dict.fromkeys([n, *n.split()]))


async def exercise_is_used(exercise_id: PydanticObjectId) -> bool:
    """Чи є вправа хоча б в одному тренуванні (колекція `trainings`)."""
    trainings = Exercise.get_pymongo_collection().database["trainings"]
    found = await trainings.find_one(
        {"sections.items.exercise_id": exercise_id}, projection={"_id": 1}
    )
    return found is not None


async def get_exercise(exercise_id: PydanticObjectId) -> Exercise:
    """Заархівовані теж повертаються: старі тренування посилаються на них."""
    exercise = await Exercise.get(exercise_id)
    if exercise is None:
        raise NotFoundError("Exercise not found")
    return exercise


async def create_exercise(payload: ExerciseIn) -> Exercise:
    exercise = Exercise(
        **payload.model_dump(), search_terms=build_search_terms(payload.name)
    )
    try:
        await exercise.insert()
    except DuplicateKeyError:
        raise ConflictError("Exercise with this slug already exists") from None
    return exercise


async def search_exercises(q: str) -> list[Exercise]:
    """Автодоповнення: префікс за `search_terms`, без заархівованих, до 10 штук."""
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


async def list_exercises(
    *,
    modality: Modality | None,
    movement_pattern: MovementPattern | None,
    muscle_groups: list[str] | None,
    equipment: list[str] | None,
    limit: int,
    offset: int,
) -> tuple[list[Exercise], int]:
    """Сторінка каталогу (без заархівованих) і загальна кількість."""
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
    return items, total


async def update_exercise(
    exercise_id: PydanticObjectId, payload: ExerciseUpdate
) -> Exercise:
    exercise = await get_exercise(exercise_id)
    changes = payload.model_dump(exclude_unset=True)

    new_modality = changes.get("modality")
    if (
        new_modality is not None
        and new_modality != exercise.modality
        and await exercise_is_used(exercise_id)
    ):
        raise ConflictError(
            "Modality cannot be changed: exercise is used in a training"
        )

    for field, value in changes.items():
        setattr(exercise, field, value)
    if "name" in changes:
        exercise.search_terms = build_search_terms(exercise.name)

    await exercise.save()
    return exercise


async def archive_exercise(exercise_id: PydanticObjectId) -> None:
    """М'яке видалення; повторний виклик нічого не змінює."""
    exercise = await get_exercise(exercise_id)
    if not exercise.is_archived:
        exercise.is_archived = True
        await exercise.save()
