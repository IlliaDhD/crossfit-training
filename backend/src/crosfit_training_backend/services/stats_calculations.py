"""Pure statistics calculations; rows are projected stored training sets.

The functions intentionally do not read a cache or persist derived records.
Changing/deleting workouts and measurements changes the next response.
"""

import datetime as dt
from bisect import bisect_right
from collections import defaultdict


def _prefer_larger_weight(candidate: dict, current: dict) -> bool:
    """Use one daily maximum; stable tie handling when order is unavailable."""
    new_weight = candidate["weight_kg"]
    old_weight = current["weight_kg"]
    return new_weight > old_weight or (
        new_weight == old_weight
        and str(candidate["training_id"]) < str(current["training_id"])
    )


def daily_strength_rows(rows: list[dict]) -> list[dict]:
    """One max weight per (date, exercise, exact reps), including all repetitions."""
    by_day: dict[tuple, dict] = {}
    for row in rows:
        key = (row["date"], str(row["exercise_id"]), row["reps"])
        old = by_day.get(key)
        if old is None or _prefer_larger_weight(row, old):
            by_day[key] = row
    return sorted(
        by_day.values(),
        key=lambda row: (row["date"], str(row["exercise_id"]), row["reps"]),
    )


def relative_strength_points(rows: list[dict], measurements: list[dict]) -> list[dict]:
    """For every training day use the last actual measurement ON OR BEFORE it."""
    weights = sorted(
        (m["date"], m["weight_kg"])
        for m in measurements
        if m.get("weight_kg") is not None and m["weight_kg"] > 0
    )
    dates = [entry[0] for entry in weights]
    result = []
    for row in daily_strength_rows(rows):
        match = bisect_right(dates, row["date"]) - 1
        measurement_date, body_weight = weights[match] if match >= 0 else (None, None)
        result.append(
            {
                "date": row["date"],
                "exercise_id": row["exercise_id"],
                "exercise_name": row["exercise_name"],
                "reps": row["reps"],
                "weight_kg": row["weight_kg"],
                "body_weight_kg": body_weight,
                "measurement_date": measurement_date,
                "relative_strength": row["weight_kg"] / body_weight if body_weight else None,
                "status": "ok" if body_weight else "insufficient_data",
                "training_id": row["training_id"],
            }
        )
    return result


def tonnage_points(rows: list[dict], group_by: str) -> list[dict]:
    """Count only qualified W sets. Complex sets are already expanded on save."""
    groups: dict[tuple, dict] = {}
    for row in rows:
        if group_by == "week":
            iso = dt.date.fromisoformat(row["date"]).isocalendar()
            key = (iso.year, iso.week)
            properties = {"year": iso.year, "week": iso.week}
        elif group_by == "exercise":
            key = (str(row["exercise_id"]),)
            properties = {
                "exercise_id": row["exercise_id"],
                "exercise_name": row["exercise_name"],
            }
        elif group_by == "movement_pattern":
            key = (row.get("movement_pattern"),)
            properties = {"movement_pattern": row.get("movement_pattern")}
        else:
            raise ValueError("Unsupported grouping")
        if key not in groups:
            groups[key] = {"group_by": group_by, "tonnage": 0.0, "sets": 0, **properties}
        groups[key]["tonnage"] += row["weight_kg"] * row["reps"]
        groups[key]["sets"] += 1
    ordered_keys = (
        sorted(groups) if group_by == "week"
        else sorted(groups, key=lambda key: str(key[0] or ""))
    )
    return [groups[key] for key in ordered_keys]


def strength_record_points(
    rows: list[dict], date_from: str | None = None, date_to: str | None = None
) -> list[dict]:
    """Find true all-time improvements BEFORE filtering visible event dates."""
    histories: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in daily_strength_rows(rows):
        histories[(str(row["exercise_id"]), row["reps"])].append(row)

    result = []
    for history in histories.values():
        previous_best = None
        for row in history:
            weight = row["weight_kg"]
            if previous_best is not None and weight <= previous_best:
                continue  # ties are not records, nor are lower weights
            improvement = weight - previous_best if previous_best is not None else None
            previous_best = weight
            if (date_from is not None and row["date"] < date_from) or (
                date_to is not None and row["date"] > date_to
            ):
                continue
            result.append(
                {
                    "date": row["date"],
                    "exercise_id": row["exercise_id"],
                    "exercise_name": row["exercise_name"],
                    "reps": row["reps"],
                    "weight_kg": weight,
                    "improvement_kg": improvement,
                    "training_id": row["training_id"],
                }
            )
    return sorted(
        result,
        key=lambda row: (row["date"], row["exercise_name"], row["reps"], str(row["exercise_id"])),
    )


def distance_best_points(rows: list[dict]) -> list[dict]:
    """A different exact exercise_id/distance must never be mixed or estimated."""
    best: dict[tuple, dict] = {}
    for row in rows:
        key = (str(row["exercise_id"]), row["distance"])
        old = best.get(key)
        if old is None or (
            (row["time_seconds"], row["date"], str(row["training_id"]))
            < (old["time_seconds"], old["date"], str(old["training_id"]))
        ):
            best[key] = row
    return [
        {
            "exercise_id": row["exercise_id"],
            "exercise_name": row["exercise_name"],
            "distance": row["distance"],
            "time_seconds": row["time_seconds"],
            "date": row["date"],
            "training_id": row["training_id"],
        }
        for row in sorted(
            best.values(),
            key=lambda r: (r["exercise_name"], str(r["exercise_id"]), r["distance"]),
        )
    ]
