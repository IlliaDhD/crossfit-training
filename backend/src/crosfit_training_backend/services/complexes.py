import re
from uuid import UUID

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from crosfit_training_backend.api.schemas.complex import ComplexIn
from crosfit_training_backend.api.schemas.sets import SetIn
from crosfit_training_backend.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from crosfit_training_backend.models.complex import Complex
from crosfit_training_backend.services.catalog import (
    check_modality,
    complex_visible_to,
    load_exercises,
)


async def validate_template_items(items: list[SetIn]) -> None:
    """A template may only use existing exercises whose modality matches the set.

    Raises 404 for a missing exercise and 422 for a modality mismatch, the same
    rules that are applied to a training when it is saved.
    """
    exercises = await load_exercises({item.exercise_id for item in items})
    for item in items:
        check_modality(exercises[item.exercise_id], item.type)


async def get_visible_complex(complex_id: PydanticObjectId, user_id: UUID) -> Complex:
    """Global or own template. Archived ones are returned too: they stay valid for
    existing logs. Someone else's template looks exactly like a missing one."""
    found = await Complex.find_one({"_id": complex_id, **complex_visible_to(user_id)})
    if found is None:
        raise NotFoundError("Complex not found")
    return found


async def create_complex(
    payload: ComplexIn, user_id: UUID, *, is_admin: bool
) -> Complex:
    """A template owned by the user; `is_global` is allowed to admins only."""
    if payload.is_global and not is_admin:
        raise ForbiddenError()
    await validate_template_items(payload.items)

    template = Complex(
        **payload.model_dump(exclude={"is_global"}),
        owner_id=None if payload.is_global else user_id,
    )
    try:
        await template.insert()
    except DuplicateKeyError:
        raise ConflictError("Complex with this slug already exists") from None
    return template


async def list_complexes(
    user_id: UUID, *, q: str | None, limit: int, offset: int
) -> tuple[list[Complex], int]:
    """Visible, non-archived templates; `q` is a case-insensitive name prefix."""
    query: dict = {"is_archived": False, **complex_visible_to(user_id)}
    if q and q.strip():
        query["name"] = {"$regex": f"^{re.escape(q.strip())}", "$options": "i"}

    found = Complex.find(query)
    total = await found.count()
    items = await found.sort("name").skip(offset).limit(limit).to_list()
    return items, total


async def archive_complex(
    complex_id: PydanticObjectId, user_id: UUID, *, is_admin: bool
) -> None:
    """Soft delete. Saved trainings are not affected: they hold expanded sets."""
    template = await get_visible_complex(complex_id, user_id)
    if template.owner_id is None and not is_admin:
        raise ForbiddenError()  # a global template is changed only by an admin
    if not template.is_archived:
        template.is_archived = True
        await template.save()
