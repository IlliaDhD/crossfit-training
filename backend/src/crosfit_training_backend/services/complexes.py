from crosfit_training_backend.api.schemas.sets import SetIn
from crosfit_training_backend.services.trainings import check_modality, load_exercises


async def validate_template_items(items: list[SetIn]) -> None:
    """A template may only use existing exercises whose modality matches the set.

    Raises 404 for a missing exercise and 422 for a modality mismatch, the same
    rules that are applied to a training when it is saved.
    """
    exercises = await load_exercises({item.exercise_id for item in items})
    for item in items:
        check_modality(exercises[item.exercise_id], item.type)
