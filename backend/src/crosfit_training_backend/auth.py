import logging
import time

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from crosfit_training_backend.exceptions import AuthError, AuthServiceUnavailableError
from crosfit_training_backend.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Keycloak signing keys are cached. The cache is refreshed when a token refers to an
# unknown `kid` (key rotation), but not more often than once per cooldown, so tokens
# with random `kid` values cannot be used to flood Keycloak with requests.
_jwks_cache: dict | None = None
_jwks_fetched_at = 0.0
JWKS_REFRESH_COOLDOWN = 30.0  # seconds


async def _fetch_jwks() -> dict:
    logger.debug("Fetching JWKS")
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=5.0) as client:
            response = await client.get(settings.KEYCLOAK_JWKS_URL)
            response.raise_for_status()
            logger.debug("Successfully fetched JWKS from Keycloak")
            return response.json()
    except httpx.HTTPError as exc:
        logger.error(f"Failed to fetch JWKS from Keycloak: {exc}")
        raise AuthServiceUnavailableError() from exc


async def _get_jwks(kid: str | None) -> dict:
    global _jwks_cache, _jwks_fetched_at
    jwks = _jwks_cache
    if jwks is None:
        known = False
        cooled_down = True
    else:
        known = any(key.get("kid") == kid for key in jwks.get("keys", []))
        cooled_down = time.monotonic() - _jwks_fetched_at >= JWKS_REFRESH_COOLDOWN
    if jwks is None or (not known and cooled_down):
        jwks = await _fetch_jwks()
        _jwks_cache = jwks
        _jwks_fetched_at = time.monotonic()
    return jwks


async def decode_token(token: str) -> dict:
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        jwks = await _get_jwks(kid)
        return jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            issuer=settings.KEYCLOAK_ISSUER,
            audience=settings.KEYCLOAK_AUDIENCE,
            # python-jose silently accepts tokens WITHOUT these claims unless they
            # are required explicitly. Signature, exp, iss and aud are verified.
            options={
                "require_exp": True,
                "require_iss": True,
                "require_aud": True,
                "require_sub": True,
            },
        )
    except ExpiredSignatureError as exc:
        raise AuthError() from exc
    except JWTError as exc:
        logger.warning(f"Failed to decode token, due to a reason: {exc}")
        raise AuthError() from exc
