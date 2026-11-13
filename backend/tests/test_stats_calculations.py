"""Pure domain tests: no Mongo or Keycloak needed."""

import pytest

from crosfit_training_backend.services.stats_calculations import (
    daily_strength_rows,
    distance_best_points,
    relative_strength_points,
    strength_record_points,
    tonnage_points,
)


def set_row(
    date,
    *,
    exercise_id="squat",
    reps=5,
    weight=100.0,
    training_id="1",
    movement_pattern="squat",
):
    return {
        "date": date,
        "exercise_id": exercise_id,
        "exercise_name": exercise_id,
        "reps": reps,
        "weight_kg": weight,
        "training_id": training_id,
        "movement_pattern": movement_pattern,
    }


def test_daily_best_is_max_not_last_and_reps_are_separate():
    rows = [
        set_row("2026-10-15", weight=100, training_id="2"),
        set_row("2026-10-15", weight=120, training_id="3"),
        set_row("2026-10-15", weight=80, training_id="1"),
        set_row("2026-10-15", reps=1, weight=150, training_id="4"),
    ]
    result = daily_strength_rows(rows)
    assert [(point["reps"], point["weight_kg"]) for point in result] == [
        (1, 150),
        (5, 120),
    ]


def test_relative_strength_uses_historical_weight_and_reports_missing():
    rows = [
        set_row("2026-10-01", weight=50),
        set_row("2026-10-05", weight=100),
        set_row("2026-10-10", weight=120),
    ]
    measurements = [
        {"date": "2026-10-03", "weight_kg": 80},
        {"date": "2026-10-09", "weight_kg": 60},
        {"date": "2026-10-20", "weight_kg": 50},
    ]
    result = relative_strength_points(rows, measurements)
    assert result[0]["status"] == "insufficient_data"
    assert result[0]["relative_strength"] is None
    assert result[0]["measurement_date"] is None
    assert result[1]["relative_strength"] == pytest.approx(1.25)
    assert result[1]["measurement_date"] == "2026-10-03"
    assert result[2]["relative_strength"] == pytest.approx(2.0)
    assert result[2]["measurement_date"] == "2026-10-09"


def test_tonnage_groups_correctly_and_crosses_iso_years():
    rows = [
        set_row("2026-12-31", weight=100, reps=5),
        set_row("2027-01-01", weight=80, reps=10),
        set_row("2027-01-04", weight=50, reps=5),
        set_row("2027-01-04", exercise_id="swing", weight=25, reps=8, movement_pattern="hinge"),
    ]
    weeks = tonnage_points(rows, "week")
    assert [(r["year"], r["week"], r["tonnage"]) for r in weeks] == [
        (2026, 53, 1300.0),
        (2027, 1, 450.0),
    ]
    patterns = tonnage_points(rows, "movement_pattern")
    assert {r["movement_pattern"]: r["tonnage"] for r in patterns} == {
        "squat": 1550.0,
        "hinge": 200.0,
    }
    exercises = tonnage_points(rows, "exercise")
    assert {r["exercise_name"]: r["sets"] for r in exercises} == {
        "squat": 3,
        "swing": 1,
    }


def test_records_ignore_equal_weights_filter_after_all_time_comparison():
    rows = [
        set_row("2026-09-01", weight=100, training_id="1"),
        set_row("2026-10-01", weight=100, training_id="2"),  # tie
        set_row("2026-10-02", weight=90, training_id="3"),
        set_row("2026-10-03", weight=120, training_id="4"),
        set_row("2026-10-03", weight=115, training_id="5"),
        set_row("2026-10-04", weight=119, training_id="6"),
        set_row("2026-10-04", weight=80, reps=1, training_id="7"),
    ]
    visible = strength_record_points(rows, "2026-10-01", "2026-10-04")
    assert [(r["date"], r["reps"], r["weight_kg"], r["improvement_kg"]) for r in visible] == [
        ("2026-10-03", 5, 120, 20),
        ("2026-10-04", 1, 80, None),
    ]
    assert visible[0]["training_id"] == "4"


def test_distance_comparison_requires_same_exercise_and_exact_distance():
    rows = [
        {"exercise_id": "run", "exercise_name": "Run", "distance": 400, "time_seconds": 80, "date": "2026-10-01", "training_id": "1"},
        {"exercise_id": "run", "exercise_name": "Run", "distance": 400, "time_seconds": 75, "date": "2026-10-02", "training_id": "2"},
        {"exercise_id": "run", "exercise_name": "Run", "distance": 500, "time_seconds": 60, "date": "2026-10-03", "training_id": "3"},
        {"exercise_id": "row", "exercise_name": "Row", "distance": 400, "time_seconds": 70, "date": "2026-10-03", "training_id": "4"},
        {"exercise_id": "run", "exercise_name": "Run", "distance": 400, "time_seconds": 75, "date": "2026-10-04", "training_id": "5"},
    ]
    result = distance_best_points(rows)
    assert {(r["exercise_id"], r["distance"]): (r["time_seconds"], r["training_id"]) for r in result} == {
        ("run", 400): (75, "2"),
        ("run", 500): (60, "3"),
        ("row", 400): (70, "4"),
    }


def test_empty_data_is_safe():
    assert relative_strength_points([], []) == []
    assert tonnage_points([], "week") == []
    assert strength_record_points([]) == []
    assert distance_best_points([]) == []
