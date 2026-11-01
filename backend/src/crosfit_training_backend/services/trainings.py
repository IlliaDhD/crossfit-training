"""Trainings: save flow (data-model.md, section 10) and CRUD rules."""

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
from crosfit_training_backend.exceptions import ForbiddenError, NotFoundError
from crosfit_training_backend.models.complex import Complex
from crosfit_training_backend.models.training import Training
from crosfit_training_backend.services.catalog import (
    check_modality,
    load_complexes,
    load_exercises,
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


# ------------------------------------------------------------------ CRUD


def iso_date_range(
    date_from: dt.date | None, date_to: dt.date | None
) -> dict[str, str]:
    """Mongo filter for the `date` field; both bounds are inclusive.

    `date` is stored as an ISO string, so string comparison equals date comparison.
    Returns an empty dict when no bound is given.
    """
    bounds: dict[str, str] = {}
    if date_from:
        bounds["$gte"] = date_from.isoformat()
    if date_to:
        bounds["$lte"] = date_to.isoformat()
    return bounds


async def get_own_training(training_id: PydanticObjectId, user_id: UUID) -> Training:
    """404 for a missing training, 403 for someone else's (data-model.md, 13)."""
    training = await Training.get(training_id)
    if training is None:
        raise NotFoundError("Training not found")
    if training.user_id != user_id:
        raise ForbiddenError()
    return training


async def create_training(payload: TrainingIn, user_id: UUID) -> Training:
    """Complex references are expanded into plain sets, every set gets a snapshot."""
    built = await build_training_doc(payload, user_id=user_id, created_by=user_id)
    training = Training(**built.model_dump())
    await training.insert()
    return training


async def list_trainings(
    user_id: UUID,
    *,
    date_from: dt.date | None,
    date_to: dt.date | None,
    limit: int,
    offset: int,
) -> tuple[list[Training], int]:
    """Own trainings, newest first, and the total count for the filter."""
    query: dict = {"user_id": user_id}
    if date_range := iso_date_range(date_from, date_to):
        query["date"] = date_range

    found = Training.find(query)
    total = await found.count()
    items = (
        await found.sort([("date", -1), ("created_at", -1)])
        .skip(offset)
        .limit(limit)
        .to_list()
    )
    return items, total


async def replace_training(
    training_id: PydanticObjectId, payload: TrainingIn, user_id: UUID
) -> Training:
    """Rebuild the whole document from the payload.

    Expanded sets are never patched by hand (data-model.md, 7.3). Ownership and
    `created_at` are kept, `updated_at` is refreshed.
    """
    training = await get_own_training(training_id, user_id)
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


async def delete_training(training_id: PydanticObjectId, user_id: UUID) -> None:
    training = await get_own_training(training_id, user_id)
    await training.delete()
