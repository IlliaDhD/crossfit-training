from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Query, Response, status

from crosfit_training_backend.api.dependencies import CurrentUser, is_admin
from crosfit_training_backend.api.schemas.complex import (
    ComplexIn,
    ComplexListOut,
    ComplexOut,
)
from crosfit_training_backend.models.complex import Complex
from crosfit_training_backend.services import complexes as complex_service

router = APIRouter(prefix="/complexes", tags=["complexes"])


@router.post("", response_model=ComplexOut, status_code=status.HTTP_201_CREATED)
async def create_complex(payload: ComplexIn, user: CurrentUser) -> Complex:
    """Create a template owned by the current user. `is_global` is admin only."""
    return await complex_service.create_complex(
        payload, user.user_id, is_admin=is_admin(user)
    )


@router.get("", response_model=ComplexListOut)
async def list_complexes(
    user: CurrentUser,
    q: Annotated[
        str | None, Query(max_length=50, description="Name prefix, case-insensitive")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ComplexListOut:
    items, total = await complex_service.list_complexes(
        user.user_id, q=q, limit=limit, offset=offset
    )
    return ComplexListOut(
        items=[ComplexOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{complex_id}", response_model=ComplexOut)
async def get_complex(complex_id: PydanticObjectId, user: CurrentUser) -> Complex:
    return await complex_service.get_visible_complex(complex_id, user.user_id)


@router.delete("/{complex_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_complex(complex_id: PydanticObjectId, user: CurrentUser) -> Response:
    await complex_service.archive_complex(
        complex_id, user.user_id, is_admin=is_admin(user)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
