"""Athlete profile and body measurement persistence and operations."""

import datetime as dt
from uuid import UUID

from pymongo import ASCENDING, DESCENDING

from crosfit_training_backend.api.schemas.profile import (
    AthleteProfileOut,
    AthleteProfilePatch,
    BodyMeasurementListOut,
    BodyMeasurementOut,
)
from crosfit_training_backend.exceptions import NotFoundError
from crosfit_training_backend.models.athlete import AthleteProfile, BodyMeasurement
from crosfit_training_backend.services.trainings import iso_date_range


async def _get_profile(user_id: UUID) -> dict:
    return await AthleteProfile.get_pymongo_collection().find_one({"user_id": user_id}) or {}


async def _update_profile(user_id: UUID, updates: dict) -> None:
    # Mongo does not allow an empty update. Distinguish an omitted field from null.
    setters = {name: value for name, value in updates.items() if value is not None}
    removals = {name: "" for name, value in updates.items() if value is None}
    changes: dict = {}
    if setters:
        changes["$set"] = setters
    if removals:
        changes["$unset"] = removals
    if not changes:
        return
    # A pure $unset upsert would produce an empty profile; this is harmless.
    await AthleteProfile.get_pymongo_collection().update_one(
        {"user_id": user_id}, changes, upsert=True
    )


async def _put_measurement(user_id: UUID, date: dt.date, weight_kg: float) -> None:
    await BodyMeasurement.get_pymongo_collection().update_one(
        {"user_id": user_id, "date": date.isoformat()},
        {"$set": {"weight_kg": weight_kg}},
        upsert=True,
    )


async def _get_measurement(user_id: UUID, date: dt.date) -> dict | None:
    return await BodyMeasurement.get_pymongo_collection().find_one(
        {"user_id": user_id, "date": date.isoformat()}
    )


async def _delete_measurement(user_id: UUID, date: dt.date) -> bool:
    result = await BodyMeasurement.get_pymongo_collection().delete_one(
        {"user_id": user_id, "date": date.isoformat()}
    )
    return result.deleted_count > 0


async def _latest_measurement(user_id: UUID, on_or_before: dt.date) -> dict | None:
    return await BodyMeasurement.get_pymongo_collection().find_one(
        {"user_id": user_id, "date": {"$lte": on_or_before.isoformat()}},
        sort=[("date", DESCENDING)],
    )


async def measurements_through(user_id: UUID, on_or_before: dt.date) -> list[dict]:
    cursor = BodyMeasurement.get_pymongo_collection().find(
        {"user_id": user_id, "date": {"$lte": on_or_before.isoformat()}}
    ).sort("date", ASCENDING)
    return await cursor.to_list(length=None)


async def _list_measurements(
    user_id: UUID,
    *,
    date_from: dt.date | None,
    date_to: dt.date | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    match: dict = {"user_id": user_id}
    if dates := iso_date_range(date_from, date_to):
        match["date"] = dates
    collection = BodyMeasurement.get_pymongo_collection()
    total = await collection.count_documents(match)
    rows = await (
        collection.find(match).sort("date", DESCENDING).skip(offset).limit(limit)
    ).to_list(length=None)
    return rows, total


async def get_athlete_profile(user_id: UUID) -> AthleteProfileOut:
    profile = await _get_profile(user_id)
    latest = await _latest_measurement(user_id, dt.date.today())
    return AthleteProfileOut(
        birth_date=profile.get("birth_date"),
        height_cm=profile.get("height_cm"),
        current_weight_kg=latest["weight_kg"] if latest else None,
        current_weight_date=latest["date"] if latest else None,
    )


async def patch_athlete_profile(
    user_id: UUID, payload: AthleteProfilePatch
) -> AthleteProfileOut:
    changes = payload.model_dump(exclude_unset=True, mode="json")
    await _update_profile(user_id, changes)
    return await get_athlete_profile(user_id)


async def measurements(
    user_id: UUID,
    *,
    date_from: dt.date | None,
    date_to: dt.date | None,
    limit: int,
    offset: int,
) -> BodyMeasurementListOut:
    rows, count = await _list_measurements(
        user_id, date_from=date_from, date_to=date_to, limit=limit, offset=offset
    )
    return BodyMeasurementListOut(
        items=[BodyMeasurementOut.model_validate(row) for row in rows],
        total=count,
        limit=limit,
        offset=offset,
    )


async def get_measurement(user_id: UUID, date: dt.date) -> BodyMeasurementOut:
    row = await _get_measurement(user_id, date)
    if row is None:
        raise NotFoundError("Body measurement not found")
    return BodyMeasurementOut.model_validate(row)


async def put_measurement(
    user_id: UUID, date: dt.date, weight_kg: float
) -> BodyMeasurementOut:
    await _put_measurement(user_id, date, weight_kg)
    return BodyMeasurementOut(date=date, weight_kg=weight_kg)


async def delete_measurement(user_id: UUID, date: dt.date) -> None:
    if not await _delete_measurement(user_id, date):
        raise NotFoundError("Body measurement not found")
