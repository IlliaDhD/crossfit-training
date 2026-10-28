"""Lookups shared by the training and complex services.

Both services must resolve exercises and complexes the same way (one query each,
the same visibility rules), so the code lives here once.
"""

from collections.abc import Iterable
from uuid import UUID

from beanie import PydanticObjectId

from crosfit_training_backend.exceptions import NotFoundError, UnprocessableError
from crosfit_training_backend.models.complex import Complex
from crosfit_training_backend.models.exercise import Exercise


def complex_visible_to(user_id: UUID) -> dict:
    """Mongo filter: global templates (owner_id is null) and the user's own."""
    return {"$or": [{"owner_id": None}, {"owner_id": user_id}]}


async def load_exercises(
    ids: Iterable[PydanticObjectId],
) -> dict[PydanticObjectId, Exercise]:
    """All exercises in ONE query. Archived ones stay valid for logs (rule 4.5).

    Raises 404 if any id is missing.
    """
    wanted = set(ids)
    if not wanted:
        return {}
    found = {
        e.id: e for e in await Exercise.find({"_id": {"$in": list(wanted)}}).to_list()
    }
    missing = wanted - found.keys()
    if missing:
        raise NotFoundError(f"Exercise not found: {sorted(map(str, missing))}")
    return found


async def load_complexes(
    ids: Iterable[PydanticObjectId], user_id: UUID
) -> dict[PydanticObjectId, Complex]:
    """All complexes in ONE query: global templates and the user's own.

    Someone else's template looks exactly like a missing one (404).
    """
    wanted = set(ids)
    if not wanted:
        return {}
    found = {
        c.id: c
        for c in await Complex.find(
            {"_id": {"$in": list(wanted)}, **complex_visible_to(user_id)}
        ).to_list()
    }
    missing = wanted - found.keys()
    if missing:
        raise NotFoundError(f"Complex not found: {sorted(map(str, missing))}")
    return found


def check_modality(exercise: Exercise, set_type: str) -> None:
    """`exercise.modality == set.type`, otherwise 422."""
    if exercise.modality != set_type:
        raise UnprocessableError(
            f"Exercise '{exercise.name}' has modality {exercise.modality}, "
            f"but the set has type {set_type}"
        )
