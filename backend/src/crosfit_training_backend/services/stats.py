"""Statistics (data-model.md, section 12).

Computed from `trainings` by aggregation. Every set holds its exercise snapshot, so
no `$lookup` is needed.
"""

import datetime as dt
from uuid import UUID

from crosfit_training_backend.models.training import Training


async def weekly_tonnage(
    user_id: UUID,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> list[dict]:
    """Tonnage (reps * weight, kg) of `W` sets per ISO week and movement pattern.

    Both dates are inclusive. `date` is an ISO string, so string comparison works.
    """
    match: dict = {"user_id": user_id}
    date_range: dict = {}
    if date_from:
        date_range["$gte"] = date_from.isoformat()
    if date_to:
        date_range["$lte"] = date_to.isoformat()
    if date_range:
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
