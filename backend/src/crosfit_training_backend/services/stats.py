"""Statistics (data-model.md, section 12).

Computed from `trainings` by aggregation. Every set holds its exercise snapshot, so
no `$lookup` is needed.
"""

import datetime as dt
from uuid import UUID

from beanie import PydanticObjectId

from crosfit_training_backend.models.training import Training
from crosfit_training_backend.services import stats_calculations as calc
from crosfit_training_backend.services.profile import measurements_through
from crosfit_training_backend.services.trainings import iso_date_range


async def weekly_tonnage(
    user_id: UUID,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> list[dict]:
    """Tonnage (reps * weight, kg) of `W` sets per ISO week and movement pattern.

    Both dates are inclusive. `date` is an ISO string, so string comparison works.
    """
    match: dict = {"user_id": user_id}
    if date_range := iso_date_range(date_from, date_to):
        match["date"] = date_range

    parsed_date = {"$dateFromString": {"dateString": "$date"}}
    pipeline = [
        {"$match": match},
        {"$unwind": "$sections"},
        {"$unwind": "$sections.items"},
        {
            "$match": {
                "sections.items.type": "W",
                "sections.items.weight": {"$ne": None},
            }
        },
        {
            "$group": {
                "_id": {
                    # the ISO week year as well: week 1 of two years must not merge
                    "year": {"$isoWeekYear": parsed_date},
                    "week": {"$isoWeek": parsed_date},
                    "pattern": "$sections.items.exercise.movement_pattern",
                },
                "tonnage": {
                    "$sum": {
                        "$multiply": ["$sections.items.reps", "$sections.items.weight"]
                    }
                },
                "sets": {"$sum": 1},
            }
        },
        {"$sort": {"_id.year": 1, "_id.week": 1, "_id.pattern": 1}},
    ]
    rows = await Training.aggregate(pipeline).to_list()
    return [
        {
            "year": row["_id"]["year"],
            "week": row["_id"]["week"],
            "movement_pattern": row["_id"]["pattern"],
            "tonnage": row["tonnage"],
            "sets": row["sets"],
        }
        for row in rows
    ]


async def _load_training_sets(
    user_id: UUID,
    *,
    modality: str,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    exercise_id: PydanticObjectId | None = None,
    reps: int | None = None,
) -> list[dict]:
    """Unwind once, retrieving only qualifying stored sets (already expanded).

    No N+1 exercise lookup: snapshots are saved in each set. The original
    training document remains the single source of truth for statistics.
    """
    match: dict = {"user_id": user_id}
    if dates := iso_date_range(date_from, date_to):
        match["date"] = dates
    item_match: dict = {"sections.items.type": modality}
    if modality == "W":
        item_match["sections.items.weight"] = {"$type": "number"}
    elif modality == "M":
        item_match["sections.items.time"] = {"$type": "number"}
        item_match["sections.items.distance"] = {"$type": "number"}
    else:
        raise ValueError("Only W and M modalities are supported")
    if exercise_id is not None:
        item_match["sections.items.exercise_id"] = exercise_id
    if reps is not None:
        item_match["sections.items.reps"] = reps
    pipeline = [
        {"$match": match},
        {"$unwind": "$sections"},
        {"$unwind": "$sections.items"},
        {"$match": item_match},
        {
            "$project": {
                "_id": 0,
                "training_id": "$_id",
                "date": 1,
                "exercise_id": "$sections.items.exercise_id",
                "exercise_name": "$sections.items.exercise.name",
                "movement_pattern": "$sections.items.exercise.movement_pattern",
                "weight_kg": "$sections.items.weight",
                "reps": "$sections.items.reps",
                "distance": "$sections.items.distance",
                "time_seconds": "$sections.items.time",
            }
        },
    ]
    return await Training.aggregate(pipeline).to_list()


async def relative_strength(
    user_id: UUID,
    *,
    exercise_id: PydanticObjectId,
    reps: int,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> list[dict]:
    sets = await _load_training_sets(
        user_id,
        modality="W",
        exercise_id=exercise_id,
        reps=reps,
        date_from=date_from,
        date_to=date_to,
    )
    if not sets:
        return []
    latest_workout_date = dt.date.fromisoformat(max(row["date"] for row in sets))
    measurements = await measurements_through(user_id, latest_workout_date)
    return calc.relative_strength_points(sets, measurements)


async def tonnage(
    user_id: UUID,
    *,
    group_by: str,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> list[dict]:
    sets = await _load_training_sets(
        user_id, modality="W", date_from=date_from, date_to=date_to
    )
    return calc.tonnage_points(sets, group_by)


async def strength_records(
    user_id: UUID,
    *,
    exercise_id: PydanticObjectId | None,
    reps: int | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> list[dict]:
    # No date bound here: PRs are computed from the whole history.
    sets = await _load_training_sets(
        user_id, modality="W", exercise_id=exercise_id, reps=reps
    )
    return calc.strength_record_points(
        sets,
        date_from.isoformat() if date_from else None,
        date_to.isoformat() if date_to else None,
    )


async def distance_bests(
    user_id: UUID, *, exercise_id: PydanticObjectId | None
) -> list[dict]:
    sets = await _load_training_sets(user_id, modality="M", exercise_id=exercise_id)
    return calc.distance_best_points(sets)
