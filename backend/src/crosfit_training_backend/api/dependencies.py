from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from crosfit_training_backend.api.schemas.user import AuthUser, TokenClaims
from crosfit_training_backend.auth import decode_token
from crosfit_training_backend.exceptions import AuthError, ForbiddenError
from crosfit_training_backend.settings import get_settings

_bearer = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> AuthUser:
    payload = await decode_token(credentials.credentials)
    try:
        claims = TokenClaims.model_validate(payload)
    except ValidationError as exc:  # token without a valid payload
        raise AuthError() from exc
    return claims.to_user(get_settings().KEYCLOAK_CLIENT_ID)


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]


def require_role(*roles: str) -> Callable[..., Awaitable[AuthUser]]:
    """Dependency factory: allows users who have at least one of `roles`.

    Usage: `user: Annotated[AuthUser, Depends(require_role("coach"))]`.
    With no roles nobody is allowed (fails closed).
    """
    allowed = frozenset(roles)

    async def checker(user: CurrentUser) -> AuthUser:
        if not allowed & user.roles:
            raise ForbiddenError()
        return user

    return checker


def is_admin(user: AuthUser) -> bool:
    """Role from KEYCLOAK_ADMIN_ROLE_NAME; an unset role means nobody is admin."""
    admin_role = get_settings().KEYCLOAK_ADMIN_ROLE
    return bool(admin_role) and admin_role in user.roles


async def require_admin(user: CurrentUser) -> AuthUser:
    if not is_admin(user):
        raise ForbiddenError()
    return user


AdminUser = Annotated[AuthUser, Depends(require_admin)]
