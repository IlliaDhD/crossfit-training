"""Validate and seed exercises. Run with: .venv/bin/python scripts/seed_exercises.py"""

import argparse
import asyncio
import json
from pathlib import Path

from crosfit_training_backend.api.schemas.exercise import ExerciseIn
from crosfit_training_backend.models.exercise import Exercise
from crosfit_training_backend.settings import get_settings
from pydantic import ConfigDict, Field, TypeAdapter, field_validator
from pymongo import AsyncMongoClient, UpdateOne
from pymongo.errors import PyMongoError


class SeedExercise(ExerciseIn):
    """Use the API's field constraints without requiring Beanie initialization."""

    model_config = ConfigDict(extra="forbid", strict=True)

    search_terms: list[str] = Field(min_length=1)
    is_archived: bool = False

    @field_validator("search_terms", "muscle_groups", "equipment")
    @classmethod
    def validate_tags(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or value != value.strip() for value in values):
            raise ValueError("Tags must be nonempty and have no surrounding whitespace")
        if len(values) != len(set(values)):
            raise ValueError("Tags must be unique")
        return values


def load_catalog(path: Path) -> list[SeedExercise]:
    """Validate the entire input before connecting to MongoDB or writing anything."""
    data = json.loads(path.read_text(encoding="utf-8"))
    exercises = TypeAdapter(list[SeedExercise]).validate_python(data, strict=True)
    if not exercises:
        raise ValueError("Catalog must contain at least one exercise")
    slugs = set()
    for exercise in exercises:
        if exercise.slug in slugs:
            raise ValueError(f"Duplicate exercise slug: {exercise.slug}")
        slugs.add(exercise.slug)
    return exercises


async def seed_exercises(exercises: list[SeedExercise], database) -> tuple[int, int]:
    collection = database[Exercise.Settings.name]
    # Share index definitions with the actual model, including its unique slug.
    await collection.create_indexes(Exercise.Settings.indexes)
    result = await collection.bulk_write(
        [
            UpdateOne(
                {"slug": exercise.slug},
                {"$setOnInsert": exercise.model_dump()},
                upsert=True,
            )
            for exercise in exercises
        ],
        ordered=True,
    )
    return result.upserted_count, result.matched_count


async def import_catalog(exercises: list[SeedExercise]) -> tuple[int, int]:
    settings = get_settings()
    async with AsyncMongoClient(
        settings.MONGO_URL, serverSelectionTimeoutMS=30000
    ) as client:
        return await seed_exercises(exercises, client[settings.MONGO_DB_NAME])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=Path("exercises.mongodb.json"))
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate without accessing MongoDB",
    )
    args = parser.parse_args()
    try:
        exercises = load_catalog(args.file)
        print(f"Validated {len(exercises)} exercises", flush=True)
        if args.validate_only:
            return
        inserted, existing = asyncio.run(import_catalog(exercises))
    except (OSError, ValueError, PyMongoError) as exc:
        parser.exit(1, f"Exercise seeding failed: {exc}\n")
    print(f"Exercise seed complete: {inserted} inserted, {existing} already present")


if __name__ == "__main__":
    main()
