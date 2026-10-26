"""Save flow of a training (data-model.md, section 10)."""

import datetime as dt
from collections.abc import Iterable
from uuid import UUID

from beanie import PydanticObjectId

from crosfit_training_backend.api.schemas.sets import (
    SET_DB_MODELS,
    ComplexMarker,
    ComplexRefIn,
    ExerciseSnapshot,
    SetIn,
)
from crosfit_training_backend.api.schemas.training import (
    SCHEMA_VERSION,
    SectionDB,
    TrainingDB,
    TrainingIn,
)
from crosfit_training_backend.exceptions import NotFoundError, UnprocessableError
from crosfit_training_backend.models.complex import Complex
from crosfit_training_backend.models.exercise import Exercise


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
            {
                "_id": {"$in": list(wanted)},
                "$or": [{"owner_id": None}, {"owner_id": user_id}],
            }
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


def _with_shared_values(component: SetIn, ref: ComplexRefIn) -> SetIn:
    """Apply the shared `weight` / `rpe` of a reference to components without own."""
    update: dict[str, float] = {}
    if (
        component.type in ("W", "G")
        and component.weight is None
        and ref.weight is not None
    ):
        update["weight"] = ref.weight
    if component.type == "W" and component.rpe is None and ref.rpe is not None:
        update["rpe"] = ref.rpe
    # values come from validated models, so no re-validation is needed
    return component.model_copy(update=update) if update else component


def _expand(
    items: Iterable, complexes: dict[PydanticObjectId, Complex]
) -> list[tuple[SetIn, ComplexMarker | None]]:
    """Replace every complex reference with plain sets repeated `rounds` times."""
    expanded: list[tuple[SetIn, ComplexMarker | None]] = []
    for item in items:
        if item.type != "complex":
            expanded.append((item, None))
            continue
        template = complexes[item.complex_id]
        for round_no in range(1, item.rounds + 1):
            marker = ComplexMarker(id=template.id, name=template.name, round=round_no)
            expanded.extend(
                (_with_shared_values(component, item), marker)
                for component in template.items
            )
    return expanded


async def build_training_doc(
    payload: TrainingIn,
    *,
    user_id: UUID,
    created_by: UUID,
    created_at: dt.datetime | None = None,
) -> TrainingDB:
    """Turn the client payload into the document that is stored.

    1. `payload` is already validated by `TrainingIn`.
    2-3. Complexes and exercises are loaded in one query each, so the number of
         queries does not depend on the number of sets.
    4. A missing exercise or complex is a 404.
    5. Complex references are expanded into plain sets with a `complex` marker.
    6. `exercise.modality == set.type` is checked for every set (422).
    7. An `exercise` snapshot is added to each set.
    8. Ownership, timestamps and `schema_version` are set.
    9. The result is validated with `TrainingDB`.
    """
    complexes = await load_complexes(payload.complex_ids(), user_id)
    exercise_ids = payload.exercise_ids() | {
        component.exercise_id
        for template in complexes.values()
        for component in template.items
    }
    exercises = await load_exercises(exercise_ids)

    sections: list[SectionDB] = []
    for section in payload.sections:
        sets = []
        for set_in, marker in _expand(section.items, complexes):
            exercise = exercises[set_in.exercise_id]
            check_modality(exercise, set_in.type)
            sets.append(
                SET_DB_MODELS[set_in.type](
                    **set_in.model_dump(),
                    exercise=ExerciseSnapshot(
                        name=exercise.name,
                        movement_pattern=exercise.movement_pattern,
                        muscle_groups=exercise.muscle_groups,
                        equipment=exercise.equipment,
                    ),
                    complex=marker,
                )
            )
        sections.append(SectionDB(**section.model_dump(exclude={"items"}), items=sets))

    # BSON `Date` has millisecond precision: keep the response of a write equal to
    # what is read back from the database
    now = dt.datetime.now(dt.UTC)
    now = now.replace(microsecond=now.microsecond // 1000 * 1000)
    return TrainingDB(
        schema_version=SCHEMA_VERSION,
        title=payload.title,
        date=payload.date,
        comment=payload.comment,
        sections=sections,
        user_id=user_id,
        created_by=created_by,
        created_at=created_at or now,  # kept when an existing training is replaced
        updated_at=now,
    )
