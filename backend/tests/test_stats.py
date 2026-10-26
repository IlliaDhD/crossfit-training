"""Integration tests: a running MongoDB is required (like for test_exercises)."""

from uuid import uuid4

from crosfit_training_backend.api.schemas.user import AuthUser


def day(catalog: dict, date: str, items: list[dict]) -> dict:
    return {
        "title": f"Training {date}",
        "date": date,
        "sections": [{"kind": "lifting", "items": items}],
    }


def squat(catalog: dict, reps: int, weight: float | None) -> dict:
    item = {"type": "W", "exercise_id": catalog["front-squat"], "reps": reps}
    if weight is not None:
        item["weight"] = weight
    return item


def swing(catalog: dict, reps: int, weight: float) -> dict:
    return {
        "type": "W",
        "exercise_id": catalog["kettlebell-swing"],
        "reps": reps,
        "weight": weight,
    }


async def test_weekly_tonnage_by_movement_pattern(client, login, user, catalog):
    login(user)
    await client.post(
        "/trainings",
        json=day(
            catalog,
            "2026-10-19",  # Monday, ISO week 43
            [
                squat(catalog, 5, 80),  # 400
                squat(catalog, 5, 80),  # 400
                swing(catalog, 15, 24),  # 360
                squat(catalog, 10, None),  # no weight: not counted
                {"type": "G", "exercise_id": catalog["pull-up"], "reps": 10},
                {"type": "M", "exercise_id": catalog["run"], "distance": 200},
            ],
        ),
    )
    await client.post(
        "/trainings",
        json=day(catalog, "2026-10-21", [squat(catalog, 3, 100)]),  # same week, 300
    )
    await client.post(
        "/trainings",
        json=day(catalog, "2026-10-26", [squat(catalog, 1, 50.5)]),  # week 44
    )

    rows = (await client.get("/stats/weekly-tonnage")).json()
    assert rows == [
        {
            "year": 2026,
            "week": 43,
            "movement_pattern": "hinge",
            "tonnage": 360.0,
            "sets": 1,
        },
        {
            "year": 2026,
            "week": 43,
            "movement_pattern": "squat",
            "tonnage": 1100.0,
            "sets": 3,
        },
        {
            "year": 2026,
            "week": 44,
            "movement_pattern": "squat",
            "tonnage": 50.5,
            "sets": 1,
        },
    ]


async def test_iso_week_year_is_part_of_the_group(client, login, user, catalog):
    login(user)
    # 2026-12-31 (Thu) and 2027-01-01 (Fri) are in ISO week 53 of 2026;
    # 2027-01-04 (Mon) starts ISO week 1 of 2027
    for date in ("2026-12-31", "2027-01-01", "2027-01-04"):
        await client.post(
            "/trainings", json=day(catalog, date, [squat(catalog, 1, 100)])
        )

    rows = (await client.get("/stats/weekly-tonnage")).json()
    assert [(r["year"], r["week"], r["tonnage"]) for r in rows] == [
        (2026, 53, 200.0),
        (2027, 1, 100.0),
    ]


async def test_stats_use_only_own_trainings_and_respect_the_range(
    client, login, user, catalog
):
    login(user)
    await client.post(
        "/trainings", json=day(catalog, "2026-10-05", [squat(catalog, 1, 100)])
    )
    await client.post(
        "/trainings", json=day(catalog, "2026-10-19", [squat(catalog, 1, 200)])
    )

    login(AuthUser(user_id=uuid4()))
    await client.post(
        "/trainings", json=day(catalog, "2026-10-19", [squat(catalog, 1, 999)])
    )

    login(user)
    everything = (await client.get("/stats/weekly-tonnage")).json()
    assert sorted(r["tonnage"] for r in everything) == [100.0, 200.0]

    ranged = (
        await client.get(
            "/stats/weekly-tonnage",
            params={"date_from": "2026-10-19", "date_to": "2026-10-19"},
        )
    ).json()
    assert [r["tonnage"] for r in ranged] == [200.0]


async def test_stats_for_a_user_without_trainings_are_empty(
    client, login, user, catalog
):
    login(user)
    assert (await client.get("/stats/weekly-tonnage")).json() == []


async def test_stats_require_authentication(client):
    assert (await client.get("/stats/weekly-tonnage")).status_code in (401, 403)
