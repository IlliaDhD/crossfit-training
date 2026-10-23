"""Integration tests: a running MongoDB is required (like for test_exercises)."""

import asyncio
import datetime as dt
from uuid import UUID, uuid4

from bson import ObjectId

from crosfit_training_backend.api.schemas.user import AuthUser
from crosfit_training_backend.models.complex import Complex
from crosfit_training_backend.models.exercise import Exercise
from crosfit_training_backend.services import trainings as trainings_service


def metcon(catalog: dict) -> dict:
    """The example metcon from data-model.md, section 6."""
    return {
        "kind": "metcon",
        "format": "amrap",
        "time_cap": 720,
        "items": [
            {"type": "G", "exercise_id": catalog["pull-up"], "reps": 10},
            {
                "type": "W",
                "exercise_id": catalog["kettlebell-swing"],
                "reps": 15,
                "weight": 24,
            },
            {"type": "M", "exercise_id": catalog["run"], "distance": 200},
        ],
        "comment": "Scaled",
    }


def training(catalog: dict, **overrides) -> dict:
    body = {
        "title": "Monday: front squat + metcon",
        "date": "2026-10-19",
        "sections": [
            {
                "kind": "lifting",
                "items": [
                    {
                        "type": "W",
                        "exercise_id": catalog["front-squat"],
                        "reps": 5,
                        "weight": 80,
                        "rpe": 8,
                    }
                ],
            },
            metcon(catalog),
        ],
    }
    return {**body, **overrides}


async def make_complex(db_catalog: dict, owner_id: UUID | None, slug="barbell-a"):
    template = Complex(
        name="Barbell complex A",
        slug=slug,
        owner_id=owner_id,
        items=[
            {"type": "W", "exercise_id": db_catalog["front-squat"], "reps": 1},
            {
                "type": "W",
                "exercise_id": db_catalog["front-squat"],
                "reps": 2,
                "weight": 100,  # own weight must win over the shared one
            },
            {"type": "G", "exercise_id": db_catalog["pull-up"], "reps": 3},
            {"type": "M", "exercise_id": db_catalog["run"], "distance": 100},
        ],
    )
    await template.insert()
    return template


# ------------------------------------------------------------------ create


async def test_create_training_adds_snapshot_and_ownership(
    client, login, user, catalog
):
    login(user)
    response = await client.post("/trainings", json=training(catalog))
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["user_id"] == str(user.user_id)
    assert body["created_by"] == str(user.user_id)
    assert body["schema_version"] == 1
    assert body["date"] == "2026-10-19"
    assert ObjectId.is_valid(body["id"])

    squat = body["sections"][0]["items"][0]
    assert squat["exercise_id"] == catalog["front-squat"]
    assert squat["exercise"] == {
        "name": "Front squat",
        "movement_pattern": "squat",
        "muscle_groups": ["quads", "glutes", "core"],
        "equipment": ["barbell"],
    }
    assert squat["complex"] is None

    run = body["sections"][1]["items"][2]
    assert run["exercise"]["name"] == "Run"
    assert (await client.get(f"/trainings/{body['id']}")).json() == body


async def test_stored_document_matches_the_data_model(client, login, db, user, catalog):
    login(user)
    created = (await client.post("/trainings", json=training(catalog))).json()

    raw = await db["trainings"].find_one({"_id": ObjectId(created["id"])})
    assert raw["date"] == "2026-10-19"  # ISO string, not a BSON date
    assert isinstance(raw["created_at"], dt.datetime)
    assert isinstance(raw["updated_at"], dt.datetime)
    assert isinstance(raw["user_id"], UUID)  # BSON UUID, standard representation
    item = raw["sections"][0]["items"][0]
    assert isinstance(item["exercise_id"], ObjectId)
    assert item["exercise"]["name"] == "Front squat"


async def test_history_does_not_change_when_exercise_is_renamed(
    client, login, user, catalog
):
    login(user)
    created = (await client.post("/trainings", json=training(catalog))).json()

    exercise = await Exercise.get(ObjectId(catalog["front-squat"]))
    exercise.name = "Renamed"
    await exercise.save()

    fetched = (await client.get(f"/trainings/{created['id']}")).json()
    assert fetched["sections"][0]["items"][0]["exercise"]["name"] == "Front squat"


async def test_modality_must_match_exercise(client, login, user, catalog):
    login(user)
    body = training(catalog)
    # pull-up is `G`, but the set claims to be a weight set
    body["sections"][0]["items"][0]["exercise_id"] = catalog["pull-up"]
    response = await client.post("/trainings", json=body)
    assert response.status_code == 422
    assert "Pull-up" in response.json()["detail"]


async def test_unknown_exercise_and_complex_return_404(client, login, user, catalog):
    login(user)
    body = training(catalog)
    body["sections"][0]["items"][0]["exercise_id"] = str(ObjectId())
    assert (await client.post("/trainings", json=body)).status_code == 404

    body = training(catalog)
    body["sections"][0]["items"] = [{"type": "complex", "complex_id": str(ObjectId())}]
    assert (await client.post("/trainings", json=body)).status_code == 404


async def test_payload_validation_returns_422(client, login, user, catalog):
    login(user)
    bad_reps = training(catalog)
    bad_reps["sections"][0]["items"][0]["reps"] = 0
    assert (await client.post("/trainings", json=bad_reps)).status_code == 422

    no_cap = training(catalog)
    del no_cap["sections"][1]["time_cap"]  # amrap needs time_cap
    assert (await client.post("/trainings", json=no_cap)).status_code == 422

    assert (
        await client.post("/trainings", json=training(catalog, sections=[]))
    ).status_code == 422
    assert (
        await client.post("/trainings", json=training(catalog, date="19.10.2026"))
    ).status_code == 422


async def test_archived_exercise_stays_valid_for_logs(client, login, user, catalog):
    login(user)
    exercise = await Exercise.get(ObjectId(catalog["front-squat"]))
    exercise.is_archived = True
    await exercise.save()
    assert (await client.post("/trainings", json=training(catalog))).status_code == 201


async def test_trainings_require_authentication(client):
    assert (await client.get("/trainings")).status_code in (401, 403)
    assert (await client.post("/trainings", json={})).status_code in (401, 403)


async def test_query_count_does_not_depend_on_number_of_sets(
    client, login, user, catalog, monkeypatch
):
    calls: list[str] = []
    for model in (Exercise, Complex):
        original = model.find

        def counted(*args, _orig=original, _name=model.__name__, **kwargs):
            calls.append(_name)
            return _orig(*args, **kwargs)

        monkeypatch.setattr(model, "find", counted)

    template = await make_complex(catalog, owner_id=None)
    login(user)

    def with_sets(n: int) -> dict:
        items = [
            {
                "type": "W",
                "exercise_id": catalog["front-squat"],
                "reps": 5,
                "weight": 60,
            }
            for _ in range(n)
        ]
        items.append({"type": "complex", "complex_id": str(template.id), "rounds": n})
        return training(catalog, sections=[{"kind": "lifting", "items": items}])

    assert (await client.post("/trainings", json=with_sets(1))).status_code == 201
    small = list(calls)
    calls.clear()
    assert (await client.post("/trainings", json=with_sets(40))).status_code == 201
    assert calls == small == ["Complex", "Exercise"]  # one query each


# ---------------------------------------------------------------- complexes


async def test_complex_is_expanded_into_plain_sets(client, login, user, catalog):
    template = await make_complex(catalog, owner_id=None)
    login(user)
    body = training(
        catalog,
        sections=[
            {
                "kind": "lifting",
                "items": [
                    {
                        "type": "complex",
                        "complex_id": str(template.id),
                        "rounds": 3,
                        "weight": 60,
                        "rpe": 7,
                    }
                ],
            }
        ],
    )
    response = await client.post("/trainings", json=body)
    assert response.status_code == 201, response.text
    items = response.json()["sections"][0]["items"]

    assert len(items) == 12  # 4 components x 3 rounds, no complex item is left
    assert all(i["type"] in ("G", "W", "M") for i in items)
    assert [i["complex"]["round"] for i in items] == [1] * 4 + [2] * 4 + [3] * 4
    assert {i["complex"]["id"] for i in items} == {str(template.id)}
    assert {i["complex"]["name"] for i in items} == {"Barbell complex A"}

    first_round = items[:4]
    assert first_round[0]["weight"] == 60 and first_round[0]["rpe"] == 7  # shared
    assert first_round[1]["weight"] == 100 and first_round[1]["rpe"] == 7  # own weight
    assert first_round[2]["weight"] == 60 and "rpe" not in first_round[2]  # G: no rpe
    assert "weight" not in first_round[3]  # M gets no shared weight
    assert first_round[3]["exercise"]["name"] == "Run"


async def test_complex_defaults_to_one_round_without_shared_values(
    client, login, user, catalog
):
    template = await make_complex(catalog, owner_id=None)
    login(user)
    body = training(
        catalog,
        sections=[
            {
                "kind": "lifting",
                "items": [{"type": "complex", "complex_id": str(template.id)}],
            }
        ],
    )
    items = (await client.post("/trainings", json=body)).json()["sections"][0]["items"]
    assert len(items) == 4
    assert items[0]["weight"] is None and items[0]["rpe"] is None


async def test_template_changes_do_not_alter_saved_training(
    client, login, user, catalog
):
    template = await make_complex(catalog, owner_id=None)
    login(user)
    body = training(
        catalog,
        sections=[
            {
                "kind": "lifting",
                "items": [{"type": "complex", "complex_id": str(template.id)}],
            }
        ],
    )
    created = (await client.post("/trainings", json=body)).json()

    template.name = "Changed"
    template.items = template.items[:1]
    await template.save()

    fetched = (await client.get(f"/trainings/{created['id']}")).json()
    assert len(fetched["sections"][0]["items"]) == 4
    assert fetched["sections"][0]["items"][0]["complex"]["name"] == "Barbell complex A"


async def test_complex_of_another_user_is_not_available(client, login, user, catalog):
    foreign = await make_complex(catalog, owner_id=uuid4(), slug="foreign")
    login(user)
    body = training(
        catalog,
        sections=[
            {
                "kind": "lifting",
                "items": [{"type": "complex", "complex_id": str(foreign.id)}],
            }
        ],
    )
    assert (await client.post("/trainings", json=body)).status_code == 404

    own = await make_complex(catalog, owner_id=user.user_id, slug="own")
    body["sections"][0]["items"][0]["complex_id"] = str(own.id)
    assert (await client.post("/trainings", json=body)).status_code == 201


async def test_modality_mismatch_inside_a_complex_returns_422(
    client, login, user, catalog
):
    template = await make_complex(catalog, owner_id=None)
    # the exercise changed its modality after the template was made
    exercise = await Exercise.get(ObjectId(catalog["run"]))
    exercise.modality = "W"
    await exercise.save()

    login(user)
    body = training(
        catalog,
        sections=[
            {
                "kind": "lifting",
                "items": [{"type": "complex", "complex_id": str(template.id)}],
            }
        ],
    )
    assert (await client.post("/trainings", json=body)).status_code == 422


# ------------------------------------------------------------------ access


async def test_user_cannot_access_foreign_training(client, login, user, catalog):
    login(user)
    created = (await client.post("/trainings", json=training(catalog))).json()
    url = f"/trainings/{created['id']}"

    login(AuthUser(user_id=uuid4()))
    assert (await client.get(url)).status_code == 403
    assert (await client.put(url, json=training(catalog))).status_code == 403
    assert (await client.delete(url)).status_code == 403

    login(user)
    assert (await client.get(url)).status_code == 200  # nothing was changed


async def test_missing_training_returns_404_and_bad_id_422(client, login, user):
    login(user)
    assert (await client.get(f"/trainings/{ObjectId()}")).status_code == 404
    assert (await client.get("/trainings/not-an-id")).status_code == 422


# -------------------------------------------------------------------- list


async def test_list_is_own_filtered_sorted_and_paginated(client, login, user, catalog):
    login(user)
    for day in ("2026-10-05", "2026-10-19", "2026-10-12", "2026-11-02"):
        await client.post("/trainings", json=training(catalog, date=day))

    login(AuthUser(user_id=uuid4()))
    await client.post("/trainings", json=training(catalog, date="2026-10-20"))
    assert (await client.get("/trainings")).json()["total"] == 1

    login(user)
    everything = (await client.get("/trainings")).json()
    assert everything["total"] == 4
    assert [i["date"] for i in everything["items"]] == [
        "2026-11-02",
        "2026-10-19",
        "2026-10-12",
        "2026-10-05",
    ]

    october = (
        await client.get(
            "/trainings", params={"date_from": "2026-10-01", "date_to": "2026-10-31"}
        )
    ).json()
    assert [i["date"] for i in october["items"]] == [
        "2026-10-19",
        "2026-10-12",
        "2026-10-05",
    ]
    # both bounds are inclusive
    exact = (
        await client.get(
            "/trainings", params={"date_from": "2026-10-12", "date_to": "2026-10-19"}
        )
    ).json()
    assert exact["total"] == 2

    page = (await client.get("/trainings", params={"limit": 2, "offset": 3})).json()
    assert page["total"] == 4
    assert [i["date"] for i in page["items"]] == ["2026-10-05"]
    assert (await client.get("/trainings", params={"limit": 1000})).status_code == 422


# ----------------------------------------------------------------- replace


async def test_put_rebuilds_the_document_and_keeps_creation_data(
    client, login, user, catalog
):
    template = await make_complex(catalog, owner_id=None)
    login(user)
    first = training(
        catalog,
        sections=[
            {
                "kind": "lifting",
                "items": [
                    {"type": "complex", "complex_id": str(template.id), "rounds": 1}
                ],
            }
        ],
    )
    created = (await client.post("/trainings", json=first)).json()
    assert len(created["sections"][0]["items"]) == 4

    await asyncio.sleep(0.01)  # BSON dates have millisecond precision
    second = {**first, "title": "Edited", "date": "2026-10-20"}
    second["sections"] = [
        {
            "kind": "lifting",
            "items": [
                {
                    "type": "complex",
                    "complex_id": str(template.id),
                    "rounds": 2,
                    "weight": 70,
                }
            ],
        }
    ]
    response = await client.put(f"/trainings/{created['id']}", json=second)
    assert response.status_code == 200, response.text
    updated = response.json()

    assert updated["id"] == created["id"]
    assert updated["title"] == "Edited"
    assert updated["date"] == "2026-10-20"
    assert len(updated["sections"][0]["items"]) == 8  # rebuilt, not patched
    assert updated["sections"][0]["items"][0]["weight"] == 70
    assert updated["created_at"] == created["created_at"]
    assert updated["created_by"] == created["created_by"]
    assert updated["updated_at"] > created["updated_at"]

    fetched = (await client.get(f"/trainings/{created['id']}")).json()
    assert fetched == updated
    assert (await client.get("/trainings")).json()["total"] == 1


async def test_put_validates_like_post_and_does_not_change_the_document(
    client, login, user, catalog
):
    login(user)
    created = (await client.post("/trainings", json=training(catalog))).json()
    url = f"/trainings/{created['id']}"

    bad = training(catalog)
    bad["sections"][0]["items"][0]["exercise_id"] = catalog["pull-up"]
    assert (await client.put(url, json=bad)).status_code == 422
    assert (await client.get(url)).json() == created


# ------------------------------------------------------------------ delete


async def test_delete_training(client, login, user, catalog):
    login(user)
    created = (await client.post("/trainings", json=training(catalog))).json()
    url = f"/trainings/{created['id']}"
    assert (await client.delete(url)).status_code == 204
    assert (await client.get(url)).status_code == 404


# ----------------------------------------------------- links with exercises


async def test_exercise_modality_is_locked_after_it_is_used_in_a_training(
    client, login, admin, user, catalog
):
    login(user)
    await client.post("/trainings", json=training(catalog))

    login(admin)
    url = f"/exercises/{catalog['front-squat']}"
    assert (await client.patch(url, json={"modality": "G"})).status_code == 409
    assert (await client.patch(url, json={"name": "New name"})).status_code == 200
    # an exercise that no training uses can still change its modality
    rope = (
        await client.post(
            "/exercises",
            json={"slug": "rope-climb", "name": "Rope climb", "modality": "G"},
        )
    ).json()
    free = f"/exercises/{rope['id']}"
    assert (await client.patch(free, json={"modality": "W"})).status_code == 200


async def test_indexes_match_the_data_model(client, db, catalog):
    async def names(collection: str) -> dict:
        return await db[collection].index_information()

    trainings_idx = await names("trainings")
    keys = {tuple(v["key"]) for v in trainings_idx.values()}
    assert (("user_id", 1), ("date", -1)) in keys
    assert (("user_id", 1), ("sections.items.exercise_id", 1)) in keys
    assert (("sections.items.complex.id", 1),) in keys

    complexes_idx = await names("complexes")
    assert complexes_idx["slug_unique"]["unique"] is True
    assert (("name", 1),) in {tuple(v["key"]) for v in complexes_idx.values()}


def test_service_exposes_build_training_doc():
    assert callable(trainings_service.build_training_doc)
