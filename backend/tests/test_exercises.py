"""Інтеграційні тести: потрібна запущена MongoDB (як і для test_trainings)."""

from bson import ObjectId

FRONT_SQUAT = {
    "slug": "front-squat",
    "name": "Front squat",
    "modality": "W",
    "movement_pattern": "squat",
    "muscle_groups": ["quads", "glutes"],
    "equipment": ["barbell"],
}
BACK_SQUAT = {**FRONT_SQUAT, "slug": "back-squat", "name": "Back squat"}
PULL_UP = {
    "slug": "pull-up",
    "name": "Pull-up",
    "modality": "G",
    "movement_pattern": "pull",
    "muscle_groups": ["lats"],
    "equipment": ["bodyweight"],
}


async def create(client, payload):
    response = await client.post("/exercises", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_admin_creates_exercise_with_generated_search_terms(client, login, admin):
    login(admin)
    body = await create(client, FRONT_SQUAT)
    assert body["search_terms"] == ["front squat", "front", "squat"]
    assert body["is_archived"] is False
    assert ObjectId.is_valid(body["id"])


async def test_regular_user_cannot_write(client, login, user):
    login(user)
    assert (await client.post("/exercises", json=FRONT_SQUAT)).status_code == 403
    assert (await client.patch(f"/exercises/{ObjectId()}", json={})).status_code == 403
    assert (await client.delete(f"/exercises/{ObjectId()}")).status_code == 403


async def test_duplicate_slug_returns_409(client, login, admin):
    login(admin)
    await create(client, FRONT_SQUAT)
    response = await client.post("/exercises", json=FRONT_SQUAT)
    assert response.status_code == 409


async def test_invalid_payload_returns_422(client, login, admin):
    login(admin)
    bad_slug = {**FRONT_SQUAT, "slug": "Bad Slug"}
    bad_modality = {**FRONT_SQUAT, "modality": "Z"}
    assert (await client.post("/exercises", json=bad_slug)).status_code == 422
    assert (await client.post("/exercises", json=bad_modality)).status_code == 422


async def test_get_exercise_and_404(client, login, admin, user):
    login(admin)
    created = await create(client, FRONT_SQUAT)
    login(user)
    response = await client.get(f"/exercises/{created['id']}")
    assert response.json()["slug"] == "front-squat"
    assert (await client.get(f"/exercises/{ObjectId()}")).status_code == 404
    assert (await client.get("/exercises/not-an-id")).status_code == 422


async def test_list_filters_and_pagination(client, login, admin, user):
    login(admin)
    for payload in (FRONT_SQUAT, BACK_SQUAT, PULL_UP):
        await create(client, payload)
    login(user)

    async def total(**params):
        return (await client.get("/exercises", params=params)).json()["total"]

    everything = (await client.get("/exercises")).json()
    assert everything["total"] == 3
    names = [i["name"] for i in everything["items"]]
    assert names == ["Back squat", "Front squat", "Pull-up"]

    assert await total(modality="G") == 1
    assert await total(movement_pattern="squat") == 2
    assert await total(equipment=["barbell", "bodyweight"]) == 3
    assert await total(muscle_groups="lats") == 1

    page = (await client.get("/exercises", params={"limit": 2, "offset": 2})).json()
    assert page["total"] == 3
    assert [i["name"] for i in page["items"]] == ["Pull-up"]
    assert (await client.get("/exercises", params={"limit": 1000})).status_code == 422


async def test_search_by_prefix_matches_any_word(client, login, admin, user):
    login(admin)
    for payload in (FRONT_SQUAT, BACK_SQUAT, PULL_UP):
        await create(client, payload)
    login(user)

    async def search(q):
        return (await client.get("/exercises/search", params={"q": q})).json()

    found = await search("squ")
    assert [i["name"] for i in found] == ["Back squat", "Front squat"]
    assert {"id", "modality"} <= set(found[0])

    assert len(await search("FRONT S")) == 1
    assert await search("quat") == []
    assert await search("([") == []  # спецсимволи regex не ламають пошук


async def test_search_is_limited_to_10(client, login, admin):
    login(admin)
    for i in range(12):
        await create(client, {**PULL_UP, "slug": f"pull-{i}", "name": f"Pull {i}"})
    found = (await client.get("/exercises/search", params={"q": "pull"})).json()
    assert len(found) == 10


async def test_patch_name_rebuilds_search_terms(client, login, admin):
    login(admin)
    created = await create(client, FRONT_SQUAT)
    response = await client.patch(
        f"/exercises/{created['id']}", json={"name": "Barbell front squat"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["search_terms"] == ["barbell front squat", "barbell", "front", "squat"]
    assert body["slug"] == "front-squat"
    assert body["modality"] == "W"  # неназвані поля не змінились


async def test_patch_rejects_null_name(client, login, admin):
    login(admin)
    created = await create(client, FRONT_SQUAT)
    response = await client.patch(f"/exercises/{created['id']}", json={"name": None})
    assert response.status_code == 422


async def test_modality_can_change_until_exercise_is_used(client, login, db, admin):
    login(admin)
    created = await create(client, FRONT_SQUAT)
    url = f"/exercises/{created['id']}"

    assert (await client.patch(url, json={"modality": "G"})).json()["modality"] == "G"

    await db["trainings"].insert_one(
        {
            "sections": [
                {"items": [{"type": "G", "exercise_id": ObjectId(created["id"])}]}
            ]
        }
    )
    assert (await client.patch(url, json={"modality": "W"})).status_code == 409
    # те саме значення і інші поля змінювати можна
    response = await client.patch(url, json={"modality": "G", "name": "New name"})
    assert response.status_code == 200


async def test_delete_archives_instead_of_removing(client, login, admin):
    login(admin)
    created = await create(client, FRONT_SQUAT)
    url = f"/exercises/{created['id']}"
    assert (await client.delete(url)).status_code == 204
    assert (await client.delete(url)).status_code == 204  # ідемпотентно

    assert (await client.get(url)).json()["is_archived"] is True
    assert (await client.get("/exercises")).json()["total"] == 0
    assert (await client.get("/exercises/search", params={"q": "front"})).json() == []
