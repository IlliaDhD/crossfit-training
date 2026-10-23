"""Tests without a database: set models, sections, complex templates, OpenAPI."""

import pytest
from bson import ObjectId
from pydantic import TypeAdapter, ValidationError

from crosfit_training_backend.api.schemas.complex import ComplexIn, ComplexTemplate
from crosfit_training_backend.api.schemas.sets import (
    CardioSetIn,
    ComplexRefIn,
    GymSetIn,
    SetIn,
    WeightSetIn,
)
from crosfit_training_backend.api.schemas.training import SectionIn, TrainingIn
from crosfit_training_backend.main import app

EX = str(ObjectId())
EX2 = str(ObjectId())
CX = str(ObjectId())

set_adapter = TypeAdapter(SetIn)


def test_discriminator_selects_the_set_model():
    assert isinstance(
        set_adapter.validate_python({"type": "G", "exercise_id": EX, "reps": 5}),
        GymSetIn,
    )
    assert isinstance(
        set_adapter.validate_python({"type": "W", "exercise_id": EX, "reps": 5}),
        WeightSetIn,
    )
    assert isinstance(
        set_adapter.validate_python({"type": "M", "exercise_id": EX, "time": 60}),
        CardioSetIn,
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "X", "exercise_id": EX, "reps": 5},  # unknown type
        {"exercise_id": EX, "reps": 5},  # no discriminator
        {"type": "W", "exercise_id": "not-an-id", "reps": 5},
        {"type": "W", "exercise_id": EX},  # reps is required
        {"type": "W", "exercise_id": EX, "reps": 0},
        {"type": "G", "exercise_id": EX, "reps": 5, "weight": 0},
        {"type": "W", "exercise_id": EX, "reps": 5, "rpe": 0.5},
        {"type": "W", "exercise_id": EX, "reps": 5, "rpe": 10.5},
        {"type": "M", "exercise_id": EX},  # cardio needs a metric
        {"type": "M", "exercise_id": EX, "time": 0},
        {"type": "M", "exercise_id": EX, "distance": -5},
    ],
)
def test_invalid_sets_are_rejected(payload):
    with pytest.raises(ValidationError):
        set_adapter.validate_python(payload)


def test_fractional_weight_and_rpe_are_valid():
    s = set_adapter.validate_python(
        {"type": "W", "exercise_id": EX, "reps": 3, "weight": 52.5, "rpe": 7.5}
    )
    assert s.weight == 52.5
    assert s.rpe == 7.5


@pytest.mark.parametrize("metric", ["time", "calories", "distance"])
def test_cardio_accepts_any_single_metric(metric):
    assert set_adapter.validate_python({"type": "M", "exercise_id": EX, metric: 10})


def test_complex_ref_defaults_to_one_round():
    ref = ComplexRefIn(type="complex", complex_id=CX)
    assert ref.rounds == 1


def test_section_format_rules():
    item = {"type": "G", "exercise_id": EX, "reps": 5}
    for fmt in ("amrap", "emom"):
        with pytest.raises(ValidationError, match="time_cap"):
            SectionIn(kind="metcon", format=fmt, items=[item])
        assert SectionIn(kind="metcon", format=fmt, time_cap=600, items=[item])
    with pytest.raises(ValidationError, match="rounds"):
        SectionIn(kind="metcon", format="for_time", items=[item])
    assert SectionIn(kind="metcon", format="for_time", rounds=3, items=[item])
    assert SectionIn(kind="warm_up", items=[item]).format == "standard"


def test_section_needs_items_and_known_kind():
    with pytest.raises(ValidationError):
        SectionIn(kind="lifting", items=[])
    with pytest.raises(ValidationError):
        SectionIn(kind="sprint", items=[{"type": "G", "exercise_id": EX, "reps": 1}])


def test_training_collects_ids_and_ignores_complex_items_for_exercises():
    training = TrainingIn.model_validate(
        {
            "title": "Mon",
            "date": "2026-10-19",
            "sections": [
                {
                    "kind": "lifting",
                    "items": [
                        {"type": "W", "exercise_id": EX, "reps": 5},
                        {"type": "complex", "complex_id": CX, "rounds": 2},
                    ],
                },
                {
                    "kind": "metcon",
                    "items": [{"type": "G", "exercise_id": EX2, "reps": 5}],
                },
            ],
        }
    )
    assert {str(i) for i in training.exercise_ids()} == {EX, EX2}
    assert {str(i) for i in training.complex_ids()} == {CX}


def test_training_requires_a_section_and_a_valid_date():
    with pytest.raises(ValidationError):
        TrainingIn(title="x", date="2026-10-19", sections=[])
    section = {
        "kind": "lifting",
        "items": [{"type": "G", "exercise_id": EX, "reps": 1}],
    }
    with pytest.raises(ValidationError):
        TrainingIn(title="x", date="2026-13-40", sections=[section])
    with pytest.raises(ValidationError):
        TrainingIn(title="", date="2026-10-19", sections=[section])


def test_nested_complexes_are_forbidden():
    nested = {"type": "complex", "complex_id": CX}
    with pytest.raises(ValidationError):
        ComplexIn(name="A", slug="a", items=[nested])
    with pytest.raises(ValidationError):
        ComplexTemplate(name="A", slug="a", items=[nested])


def test_complex_needs_items():
    with pytest.raises(ValidationError):
        ComplexIn(name="A", slug="a", items=[])


def test_openapi_describes_trainings_complexes_and_units():
    spec = app.openapi()
    paths = spec["paths"]
    assert set(paths["/trainings"]) == {"get", "post"}
    assert set(paths["/trainings/{training_id}"]) == {"get", "put", "delete"}
    assert set(paths["/complexes"]) == {"get", "post"}
    assert "/stats/weekly-tonnage" in paths
    assert "/workouts" not in paths

    schemas = spec["components"]["schemas"]
    assert (
        schemas["WeightSetIn"]["properties"]["weight"]["anyOf"][0]["type"] == "number"
    )
    assert "kilograms" in str(schemas["WeightSetIn"]["properties"]["weight"])
    assert "seconds" in str(schemas["CardioSetIn"]["properties"]["time"])
    assert "meters" in str(schemas["CardioSetIn"]["properties"]["distance"])
