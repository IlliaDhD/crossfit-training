import re
from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query, Response, status
from pymongo.errors import DuplicateKeyError

from crosfit_training_backend.api.dependencies import CurrentUser, is_admin
from crosfit_training_backend.api.schemas.complex import (
    ComplexIn,
    ComplexListOut,
    ComplexOut,
)
from crosfit_training_backend.api.schemas.user import AuthUser
from crosfit_training_backend.exceptions import ForbiddenError, NotFoundError
from crosfit_training_backend.models.complex import Complex
from crosfit_training_backend.services.complexes import validate_template_items

router = APIRouter(prefix="/complexes", tags=["complexes"])


def _visible_to(user: AuthUser) -> dict:
    """Global templates (owner_id is null) and the user's own."""
    return {"$or": [{"owner_id": None}, {"owner_id": user.user_id}]}


async def _get_visible_or_404(complex_id: PydanticObjectId, user: AuthUser) -> Complex:
    found = await Complex.find_one({"_id": complex_id, **_visible_to(user)})
    if found is None:
        raise NotFoundError("Complex not found")
    return found


@router.post("", response_model=ComplexOut, status_code=status.HTTP_201_CREATED)
async def create_complex(payload: ComplexIn, user: CurrentUser) -> Complex:
    """Create a template owned by the current user. `is_global` is admin only."""
    if payload.is_global and not is_admin(user):
        raise ForbiddenError()
    await validate_template_items(payload.items)

    template = Complex(
        **payload.model_dump(exclude={"is_global"}),
        owner_id=None if payload.is_global else user.user_id,
    )
    try:
        await template.insert()
    except DuplicateKeyError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Complex with this slug already exists"
        ) from None
    return template


@router.get("", response_model=ComplexListOut)
async def list_complexes(
    user: CurrentUser,
    q: Annotated[
        str | None, Query(max_length=50, description="Name prefix, case-insensitive")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ComplexListOut:
    query: dict = {"is_archived": False, **_visible_to(user)}
    if q and q.strip():
        query["name"] = {"$regex": f"^{re.escape(q.strip())}", "$options": "i"}

    found = Complex.find(query)
    total = await found.count()
    items = await found.sort("name").skip(offset).limit(limit).to_list()
    return ComplexListOut(
        items=[ComplexOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{complex_id}", response_model=ComplexOut)
async def get_complex(complex_id: PydanticObjectId, user: CurrentUser) -> Complex:
    # archived templates are returned too: they stay valid for existing logs
    return await _get_visible_or_404(complex_id, user)


@router.delete("/{complex_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_complex(complex_id: PydanticObjectId, user: CurrentUser) -> Response:
    """Soft delete. Saved trainings are not affected: they hold expanded sets."""
    template = await _get_visible_or_404(complex_id, user)
    if template.owner_id is None and not is_admin(user):
        raise ForbiddenError()  # a global template is changed only by an admin
    if not template.is_archived:
        template.is_archived = True
        await template.save()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
