"""Integration tests: a running MongoDB is required (like for test_exercises)."""

from bson import ObjectId

from crosfit_training_backend.api.schemas.user import AuthUser


def complex_body(catalog: dict, **overrides) -> dict:
    body = {
        "name": "Barbell complex A",
        "slug": "barbell-complex-a",
        "tags": ["barbell", "olympic"],
        "items": [
            {"type": "W", "exercise_id": catalog["front-squat"], "reps": 1},
            {"type": "W", "exercise_id": catalog["front-squat"], "reps": 2},
            {"type": "G", "exercise_id": catalog["pull-up"], "reps": 3},
        ],
    }
    return {**body, **overrides}


async def test_user_creates_own_complex(client, login, user, catalog):
    login(user)
    response = await client.post("/complexes", json=complex_body(catalog))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["owner_id"] == str(user.user_id)
    assert body["format"] == "standard" and body["is_archived"] is False
    assert len(body["items"]) == 3
    assert ObjectId.is_valid(body["id"])


async def test_only_admin_creates_global_complex(client, login, user, admin, catalog):
    login(user)
    payload = complex_body(catalog, is_global=True)
    assert (await client.post("/complexes", json=payload)).status_code == 403

    login(admin)
    response = await client.post("/complexes", json=payload)
    assert response.status_code == 201
    assert response.json()["owner_id"] is None

    # a global template is visible to everyone
    login(user)
    assert (await client.get(f"/complexes/{response.json()['id']}")).status_code == 200


async def test_complex_validation(client, login, user, catalog):
    login(user)
    nested = complex_body(
        catalog, items=[{"type": "complex", "complex_id": str(ObjectId())}]
    )
    assert (await client.post("/complexes", json=nested)).status_code == 422
    assert (
        await client.post("/complexes", json=complex_body(catalog, items=[]))
    ).status_code == 422
    assert (
        await client.post("/complexes", json=complex_body(catalog, slug="Bad Slug"))
    ).status_code == 422

    wrong_modality = complex_body(
        catalog,
        items=[{"type": "W", "exercise_id": catalog["pull-up"], "reps": 5}],
    )
    assert (await client.post("/complexes", json=wrong_modality)).status_code == 422

    unknown = complex_body(
        catalog, items=[{"type": "W", "exercise_id": str(ObjectId()), "reps": 5}]
    )
    assert (await client.post("/complexes", json=unknown)).status_code == 404


async def test_duplicate_slug_returns_409(client, login, user, catalog):
    login(user)
    assert (
        await client.post("/complexes", json=complex_body(catalog))
    ).status_code == 201
    assert (
        await client.post("/complexes", json=complex_body(catalog))
    ).status_code == 409


async def test_complexes_are_private_to_their_owner(client, login, user, catalog):
    login(user)
    created = (await client.post("/complexes", json=complex_body(catalog))).json()

    login(AuthUser(user_id=user.user_id.__class__(int=1)))
    assert (await client.get(f"/complexes/{created['id']}")).status_code == 404
    assert (await client.get("/complexes")).json()["total"] == 0
    assert (await client.delete(f"/complexes/{created['id']}")).status_code == 404


async def test_list_search_and_pagination(client, login, user, catalog):
    login(user)
    for slug, name in (("a", "Alpha complex"), ("b", "Beta complex"), ("c", "alpine")):
        await client.post(
            "/complexes", json=complex_body(catalog, slug=slug, name=name)
        )

    everything = (await client.get("/complexes")).json()
    assert [i["name"] for i in everything["items"]] == [
        "Alpha complex",
        "Beta complex",
        "alpine",
    ]
    found = (await client.get("/complexes", params={"q": "alp"})).json()
    assert {i["name"] for i in found["items"]} == {"Alpha complex", "alpine"}
    assert (await client.get("/complexes", params={"q": "(["})).json()["total"] == 0

    page = (await client.get("/complexes", params={"limit": 1, "offset": 2})).json()
    assert page["total"] == 3 and len(page["items"]) == 1


async def test_archive_hides_from_list_but_not_from_get(client, login, user, catalog):
    login(user)
    created = (await client.post("/complexes", json=complex_body(catalog))).json()
    url = f"/complexes/{created['id']}"
    assert (await client.delete(url)).status_code == 204
    assert (await client.delete(url)).status_code == 204  # idempotent

    assert (await client.get("/complexes")).json()["total"] == 0
    assert (await client.get(url)).json()["is_archived"] is True


async def test_global_complex_is_archived_only_by_admin(
    client, login, user, admin, catalog
):
    login(admin)
    created = (
        await client.post("/complexes", json=complex_body(catalog, is_global=True))
    ).json()
    url = f"/complexes/{created['id']}"

    login(user)
    assert (await client.delete(url)).status_code == 403
    login(admin)
    assert (await client.delete(url)).status_code == 204
