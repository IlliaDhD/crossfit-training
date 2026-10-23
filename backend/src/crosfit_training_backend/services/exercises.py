from beanie import PydanticObjectId

from crosfit_training_backend.models.exercise import Exercise


def build_search_terms(name: str) -> list[str]:
    """Повна назва в нижньому регістрі + кожне слово назви (без дублікатів)."""
    n = name.lower().strip()
    return list(dict.fromkeys([n, *n.split()]))


async def exercise_is_used(exercise_id: PydanticObjectId) -> bool:
    """Чи є вправа хоча б в одному тренуванні (колекція `trainings`)."""
    trainings = Exercise.get_pymongo_collection().database["trainings"]
    found = await trainings.find_one(
        {"sections.items.exercise_id": exercise_id}, projection={"_id": 1}
    )
    return found is not None
