"""Tests without a database: schemas, search_terms, auth, OpenAPI."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from crosfit_training_backend.api.schemas.exercise import (
    ExerciseIn,
    ExerciseUpdate,
)
from crosfit_training_backend.main import app
from crosfit_training_backend.services.exercises import build_search_terms


def test_build_search_terms():
    assert build_search_terms("Front Squat") == ["front squat", "front", "squat"]


def test_build_search_terms_single_word_has_no_duplicate():
    assert build_search_terms(" Deadlift ") == ["deadlift"]


@pytest.mark.parametrize("slug", ["Front Squat", "front_squat", "", "фронт"])
def test_exercise_in_rejects_bad_slug(slug):
    with pytest.raises(ValidationError):
        ExerciseIn(slug=slug, name="X", modality="W")


def test_exercise_in_rejects_unknown_modality():
    with pytest.raises(ValidationError):
        ExerciseIn.model_validate({"slug": "x", "name": "X", "modality": "Z"})


def test_exercise_update_forbids_null_for_required_fields():
    with pytest.raises(ValidationError):
        ExerciseUpdate(name=None)
    assert ExerciseUpdate(movement_pattern=None).movement_pattern is None


async def test_exercises_require_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        response = await c.get("/exercises")
    assert response.status_code in (401, 403)


def test_openapi_is_generated():
    spec = app.openapi()
    assert {"/exercises", "/exercises/search", "/exercises/{exercise_id}"} <= set(
        spec["paths"]
    )
    assert set(spec["paths"]["/exercises/{exercise_id}"]) == {"get", "patch", "delete"}
    assert "ExerciseIn" in spec["components"]["schemas"]
