"""Integration tests for athlete profiles and statistics in the standard API."""

from uuid import uuid4

from crosfit_training_backend.api.schemas.user import AuthUser


def workout(date, items):
    return {
        "title": f"Workout {date}",
        "date": date,
        "sections": [{"kind": "lifting", "items": items}],
    }


def weighted(exercise_id, weight, reps=5):
    item = {"type": "W", "exercise_id": exercise_id, "reps": reps}
    if weight is not None:
        item["weight"] = weight
    return item


async def post_workout(client, date, items):
    response = await client.post("/trainings", json=workout(date, items))
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_profile_and_measurements_are_private_and_editable(client, login, user):
    login(user)
    initial = await client.get("/me/profile")
    assert initial.status_code == 200
    assert initial.json() == {
        "birth_date": None,
        "height_cm": None,
        "current_weight_kg": None,
        "current_weight_date": None,
    }

    response = await client.patch(
        "/me/profile", json={"birth_date": "2001-04-12", "height_cm": 181}
    )
    assert response.status_code == 200, response.text
    assert response.json()["height_cm"] == 181
    assert (await client.patch("/me/profile", json={"height_cm": None})).json()[
        "birth_date"
    ] == "2001-04-12"
    assert (await client.get("/me/profile")).json()["height_cm"] is None

    first = "/me/body-measurements/2026-10-01"
    assert (await client.put(first, json={"weight_kg": 82})).status_code == 200
    assert (await client.put(first, json={"weight_kg": 81})).status_code == 200
    assert (
        await client.put(
            "/me/body-measurements/2026-10-02", json={"weight_kg": 80}
        )
    ).status_code == 200
    listing = (await client.get("/me/body-measurements")).json()
    assert listing["total"] == 2
    assert [(item["date"], item["weight_kg"]) for item in listing["items"]] == [
        ("2026-10-02", 80.0),
        ("2026-10-01", 81.0),
    ]

    login(AuthUser(user_id=uuid4()))
    assert (await client.get("/me/profile")).json()["birth_date"] is None
    assert (await client.get("/me/body-measurements")).json()["total"] == 0
    assert (await client.get(first)).status_code == 404
    assert (await client.delete(first)).status_code == 404

    login(user)
    assert (await client.delete(first)).status_code == 204
    assert (await client.get(first)).status_code == 404
    assert (await client.get("/me/body-measurements")).json()["total"] == 1


async def test_relative_strength_historical_weight_and_live_updates(
    client, login, user, catalog
):
    login(user)
    exercise = catalog["front-squat"]
    first = await post_workout(client, "2026-10-01", [weighted(exercise, 100)])
    second = await post_workout(
        client, "2026-10-05", [weighted(exercise, 90), weighted(exercise, 120)]
    )
    url = "/stats/relative-strength"
    params = {"exercise_id": exercise, "reps": 5}
    before = (await client.get(url, params=params)).json()
    assert len(before) == 2
    assert all(row["status"] == "insufficient_data" for row in before)

    assert (
        await client.put(
            "/me/body-measurements/2026-10-03", json={"weight_kg": 80}
        )
    ).status_code == 200
    after = (await client.get(url, params=params)).json()
    assert after[0]["relative_strength"] is None  # future measurement not used
    assert after[1]["relative_strength"] == 1.5
    assert after[1]["measurement_date"] == "2026-10-03"
    assert after[1]["training_id"] == second

    assert (
        await client.put(
            "/me/body-measurements/2026-10-03", json={"weight_kg": 60}
        )
    ).status_code == 200
    edited = (await client.get(url, params=params)).json()
    assert edited[1]["relative_strength"] == 2.0

    assert (
        await client.delete("/me/body-measurements/2026-10-03")
    ).status_code == 204
    no_measurement = (await client.get(url, params=params)).json()
    assert no_measurement[1]["status"] == "insufficient_data"

    assert (await client.delete(f"/trainings/{second}")).status_code == 204
    assert len((await client.get(url, params=params)).json()) == 1
    assert (await client.delete(f"/trainings/{first}")).status_code == 204
    assert (await client.get(url, params=params)).json() == []


async def test_records_date_filter_repetitions_and_user_isolation(
    client, login, user, catalog
):
    login(user)
    exercise = catalog["front-squat"]
    await post_workout(client, "2026-09-01", [weighted(exercise, 100)])
    await post_workout(client, "2026-10-01", [weighted(exercise, 100)])
    await post_workout(client, "2026-10-02", [weighted(exercise, 95)])
    best_id = await post_workout(
        client, "2026-10-03", [weighted(exercise, 110), weighted(exercise, 120)]
    )
    await post_workout(client, "2026-10-04", [weighted(exercise, 90, reps=1)])

    login(AuthUser(user_id=uuid4()))
    await post_workout(client, "2026-10-03", [weighted(exercise, 999)])
    assert (await client.get("/stats/strength-records")).json()[-1]["weight_kg"] == 999.0

    login(user)
    records = (
        await client.get(
            "/stats/strength-records",
            params={"date_from": "2026-10-01", "date_to": "2026-10-04"},
        )
    ).json()
    assert [(r["date"], r["reps"], r["weight_kg"]) for r in records] == [
        ("2026-10-03", 5, 120.0),
        ("2026-10-04", 1, 90.0),
    ]
    assert records[0]["improvement_kg"] == 20.0
    assert records[0]["training_id"] == best_id
    assert records[1]["improvement_kg"] is None


async def test_tonnage_excludes_missing_weight_and_counts_expanded_rounds_once(
    client, login, user, catalog
):
    login(user)
    exercise = catalog["front-squat"]
    template = (
        await client.post(
            "/complexes",
            json={
                "name": "Squat repeat",
                "slug": "squat-repeat",
                "items": [weighted(exercise, 20, reps=2)],
            },
        )
    )
    assert template.status_code == 201, template.text
    template_id = template.json()["id"]
    await post_workout(
        client,
        "2026-10-19",
        [
            {"type": "complex", "complex_id": template_id, "rounds": 3},
            weighted(exercise, None, reps=10),
            {"type": "G", "exercise_id": catalog["pull-up"], "reps": 10},
        ],
    )
    tonnage = (await client.get("/stats/tonnage")).json()
    assert len(tonnage) == 1
    assert tonnage[0]["tonnage"] == 120.0  # 2*20*3, not rounds squared
    assert tonnage[0]["sets"] == 3
    by_exercise = (
        await client.get("/stats/tonnage", params={"group_by": "exercise"})
    ).json()
    assert by_exercise[0]["exercise_name"] == "Front squat"
    assert by_exercise[0]["tonnage"] == 120.0
    legacy = (await client.get("/stats/weekly-tonnage")).json()
    assert legacy[0]["tonnage"] == 120.0


async def test_cardio_exact_exercise_and_distance_and_bad_ranges(
    client, login, user, catalog
):
    login(user)
    run = catalog["run"]
    await post_workout(
        client,
        "2026-10-05",
        [
            {"type": "M", "exercise_id": run, "distance": 400, "time": 85},
            {"type": "M", "exercise_id": run, "distance": 500, "time": 65},
            {"type": "M", "exercise_id": run, "distance": 600},
        ],
    )
    await post_workout(
        client, "2026-10-06", [{"type": "M", "exercise_id": run, "distance": 400, "time": 75}]
    )
    bests = (await client.get("/stats/distance-bests")).json()
    assert [(r["distance"], r["time_seconds"]) for r in bests] == [
        (400, 75), (500, 65)
    ]
    assert (await client.get("/stats/distance-bests", params={"exercise_id": run})).status_code == 200
    assert (
        await client.get(
            "/stats/tonnage", params={"date_from": "2026-11-01", "date_to": "2026-01-01"}
        )
    ).status_code == 422
    assert (await client.put("/me/body-measurements/2026-10-07", json={"weight_kg": -1})).status_code == 422


async def test_athlete_indexes_are_initialized_with_database(db):
    profiles = await db.athlete_profiles.index_information()
    measurements = await db.body_measurements.index_information()
    assert profiles["user_unique"]["unique"] is True
    assert profiles["user_unique"]["key"] == [("user_id", 1)]
    assert measurements["user_date_unique"]["unique"] is True
    assert measurements["user_date_unique"]["key"] == [("user_id", 1), ("date", 1)]
