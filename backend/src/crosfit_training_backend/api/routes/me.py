from fastapi import APIRouter

from crosfit_training_backend.api.dependencies import CurrentUser
from crosfit_training_backend.api.schemas.user import AuthUser

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=AuthUser)
async def read_me(user: CurrentUser) -> AuthUser:
    """Who the access token belongs to: `user_id` (sub), username and roles."""
    return user
