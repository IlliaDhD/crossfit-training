from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pymongo import AsyncMongoClient

from crosfit_training_backend.api import dependencies
from crosfit_training_backend.api.dependencies import get_current_user
from crosfit_training_backend.api.schemas.user import AuthUser
from crosfit_training_backend.database import init_db
from crosfit_training_backend.main import app
from crosfit_training_backend.models.exercise import Exercise
from crosfit_training_backend.services.exercises import build_search_terms
from crosfit_training_backend.settings import get_settings

TEST_DB = "crossfit_test"


@pytest.fixture(autouse=True)
def _fixed_auth_settings(monkeypatch):
    """Roles in tests do not depend on Keycloak environment variables."""
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(
            KEYCLOAK_ADMIN_ROLE="admin", KEYCLOAK_CLIENT_ID="crossfit"
        ),
    )


@pytest.fixture
def admin() -> AuthUser:
    return AuthUser(user_id=uuid4(), username="admin", roles=frozenset({"admin"}))


@pytest.fixture
def user() -> AuthUser:
    return AuthUser(user_id=uuid4(), username="user", roles=frozenset({"athlete"}))


@pytest.fixture
def login():
    """login(admin) / login(user): replaces the current user without Keycloak."""

    def _login(user: AuthUser) -> None:
        app.dependency_overrides[get_current_user] = lambda: user

    yield _login
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db():
    mongo = AsyncMongoClient(
        get_settings().MONGO_URL,
        uuidRepresentation="standard",
        serverSelectionTimeoutMS=3000,
    )
    await init_db(mongo, TEST_DB)
    yield mongo[TEST_DB]
    await mongo.drop_database(TEST_DB)
    await mongo.close()


@pytest_asyncio.fixture
async def client(db):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


CATALOG = {
    # slug: (name, modality, movement_pattern, muscle_groups, equipment)
    "pull-up": ("Pull-up", "G", "pull", ["lats"], ["bodyweight"]),
    "kettlebell-swing": ("Kettlebell swing", "W", "hinge", ["glutes"], ["kettlebell"]),
    "front-squat": (
        "Front squat",
        "W",
        "squat",
        ["quads", "glutes", "core"],
        ["barbell"],
    ),
    "run": ("Run", "M", "locomotion", ["legs"], ["bodyweight"]),
}


@pytest_asyncio.fixture
async def catalog(db) -> dict[str, str]:
    """Seeds the exercise catalog and returns `{slug: id as str}`."""
    ids: dict[str, str] = {}
    for slug, (name, modality, pattern, muscles, equipment) in CATALOG.items():
        exercise = Exercise(
            slug=slug,
            name=name,
            search_terms=build_search_terms(name),
            modality=modality,
            movement_pattern=pattern,
            muscle_groups=muscles,
            equipment=equipment,
        )
        await exercise.insert()
        ids[slug] = str(exercise.id)
    return ids
