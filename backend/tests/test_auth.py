"""Authentication tests with real RSA-signed tokens. No Keycloak and no database."""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Annotated
from uuid import UUID, uuid4

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwk, jwt

from crosfit_training_backend import auth
from crosfit_training_backend.api.dependencies import get_current_user, require_role
from crosfit_training_backend.api.error_handlers import register_error_handlers
from crosfit_training_backend.api.schemas.user import AuthUser, TokenClaims
from crosfit_training_backend.auth import decode_token
from crosfit_training_backend.exceptions import AuthError, AuthServiceUnavailableError
from crosfit_training_backend.main import app

ISSUER = "http://localhost:8080/realms/crossfit"
AUDIENCE = "crossfit-api"
JWKS_URL = f"{ISSUER}/protocol/openid-connect/certs"
SUB = "3f1c2d9e-8a4b-4c6e-9f10-1a2b3c4d5e6f"


@dataclass
class KeyPair:
    private_pem: str
    public_pem: str

    @classmethod
    def generate(cls) -> "KeyPair":
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        public = key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return cls(private.decode(), public.decode())

    def jwk(self, kid: str) -> dict:
        return {**jwk.construct(self.public_pem, "RS256").to_dict(), "kid": kid}


@pytest.fixture(scope="session")
def key1() -> KeyPair:
    return KeyPair.generate()


@pytest.fixture(scope="session")
def key2() -> KeyPair:
    return KeyPair.generate()


def make_token(key: KeyPair, kid: str = "k1", **claims) -> str:
    """Valid token by default. Pass a claim as None to remove it."""
    payload = {
        "iss": ISSUER,
        "aud": [AUDIENCE, "account"],
        "sub": SUB,
        "preferred_username": "coach",
        "exp": int(time.time()) + 300,
        "realm_access": {"roles": ["coach"]},
        "resource_access": {"crossfit": {"roles": ["extra"]}},
        **claims,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    return jwt.encode(payload, key.private_pem, algorithm="RS256", headers={"kid": kid})


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def forge(header: dict, secret: bytes | None = None, **claims) -> str:
    """Hand-made token: alg=none (secret None) or HMAC signed with `secret`."""
    payload = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": SUB,
        "exp": int(time.time()) + 300,
    }
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(payload | claims).encode())}"
    signature = b""
    if secret is not None:
        signature = hmac.new(secret, signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(signature)}"


class FakeKeycloak:
    """Stands in for the JWKS endpoint and counts how often it is called."""

    def __init__(self, key1: KeyPair) -> None:
        self.keys = {"k1": key1}
        self.fetches = 0

    async def fetch(self) -> dict:
        self.fetches += 1
        return {"keys": [key.jwk(kid) for kid, key in self.keys.items()]}


@pytest.fixture
def keycloak(monkeypatch, key1) -> FakeKeycloak:
    fake = FakeKeycloak(key1)
    monkeypatch.setattr(
        auth,
        "settings",
        SimpleNamespace(
            KEYCLOAK_ISSUER=ISSUER,
            KEYCLOAK_AUDIENCE=AUDIENCE,
            KEYCLOAK_JWKS_URL=JWKS_URL,
        ),
    )
    monkeypatch.setattr(auth, "_jwks_cache", None)
    monkeypatch.setattr(auth, "_jwks_fetched_at", 0.0)
    monkeypatch.setattr(auth, "_fetch_jwks", fake.fetch)
    return fake


@pytest.fixture
async def http():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


# --- JWT validation ---------------------------------------------------------------


async def test_valid_token_is_accepted(keycloak, key1):
    payload = await decode_token(make_token(key1))
    assert payload["sub"] == SUB


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": int(time.time()) - 10},  # expired
        {"exp": None},  # no exp
        {"iss": "http://evil.example/realms/crossfit"},  # wrong issuer
        {"iss": None},  # no issuer
        {"aud": "another-api"},  # wrong audience
        {"aud": ["account"]},  # Keycloak default audience only
        {"aud": None},  # no audience
        {"sub": None},  # no subject
    ],
    ids=[
        "expired",
        "no-exp",
        "wrong-iss",
        "no-iss",
        "wrong-aud",
        "default-aud-only",
        "no-aud",
        "no-sub",
    ],
)
async def test_invalid_claims_are_rejected(keycloak, key1, claims):
    with pytest.raises(AuthError):
        await decode_token(make_token(key1, **claims))


async def test_token_signed_with_foreign_key_is_rejected(keycloak, key2):
    with pytest.raises(AuthError):
        await decode_token(make_token(key2, kid="k1"))


async def test_unsigned_token_is_rejected(keycloak):
    with pytest.raises(AuthError):
        await decode_token(forge({"alg": "none", "typ": "JWT", "kid": "k1"}))


async def test_hs256_signed_with_public_key_is_rejected(keycloak, key1):
    token = forge(
        {"alg": "HS256", "typ": "JWT", "kid": "k1"}, secret=key1.public_pem.encode()
    )
    with pytest.raises(AuthError):
        await decode_token(token)


@pytest.mark.parametrize("token", ["", "not-a-jwt", "a.b.c"])
async def test_garbage_is_rejected(keycloak, token):
    with pytest.raises(AuthError):
        await decode_token(token)


# --- JWKS cache -------------------------------------------------------------------


async def test_jwks_is_cached(keycloak, key1):
    for _ in range(3):
        await decode_token(make_token(key1))
    assert keycloak.fetches == 1


async def test_key_rotation_refreshes_jwks_once(monkeypatch, keycloak, key1, key2):
    monkeypatch.setattr(auth, "JWKS_REFRESH_COOLDOWN", 0.0)
    await decode_token(make_token(key1))
    keycloak.keys = {"k2": key2}  # Keycloak rotated its keys

    await decode_token(make_token(key2, kid="k2"))
    assert keycloak.fetches == 2


async def test_unknown_kid_refetch_is_rate_limited(keycloak, key1, key2):
    await decode_token(make_token(key1))
    keycloak.keys["k2"] = key2

    with pytest.raises(AuthError):  # inside the cooldown: no refetch
        await decode_token(make_token(key2, kid="k2"))
    assert keycloak.fetches == 1


@pytest.fixture
def mock_keycloak_http(monkeypatch):
    """Replaces the real HTTP call to Keycloak with a handler."""
    monkeypatch.setattr(
        auth,
        "settings",
        SimpleNamespace(
            KEYCLOAK_ISSUER=ISSUER,
            KEYCLOAK_AUDIENCE=AUDIENCE,
            KEYCLOAK_JWKS_URL=JWKS_URL,
        ),
    )
    monkeypatch.setattr(auth, "_jwks_cache", None)
    original = httpx.AsyncClient

    def install(handler):
        monkeypatch.setattr(
            auth.httpx,
            "AsyncClient",
            lambda **_: original(transport=httpx.MockTransport(handler)),
        )

    return install


async def test_jwks_is_downloaded_from_keycloak(mock_keycloak_http, key1):
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, json={"keys": [key1.jwk("k1")]})

    mock_keycloak_http(handler)
    await decode_token(make_token(key1))
    assert requested == [JWKS_URL]


async def test_keycloak_down_gives_503(mock_keycloak_http, key1, http):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    mock_keycloak_http(handler)
    with pytest.raises(AuthServiceUnavailableError):
        await decode_token(make_token(key1))

    response = await http.get(
        "/me", headers={"Authorization": f"Bearer {make_token(key1)}"}
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication service is unavailable"}


# --- get_current_user through the real app (GET /me) --------------------------------


async def test_me_returns_user_from_token(keycloak, key1, http):
    response = await http.get(
        "/me", headers={"Authorization": f"Bearer {make_token(key1)}"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "user_id": SUB,
        "username": "coach",
        "roles": ["coach", "extra"],  # realm role + role of client "crossfit"
    }


async def test_me_without_token_is_unauthorized(http):
    assert (await http.get("/me")).status_code in (401, 403)


async def test_me_with_invalid_token_is_401_with_challenge(keycloak, key1, http):
    token = make_token(key1, exp=int(time.time()) - 10)
    response = await http.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Invalid credentials"}


async def test_me_with_non_uuid_subject_is_401(keycloak, key1, http):
    token = make_token(key1, sub="not-a-uuid")
    response = await http.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_token_claims_to_user_merges_realm_and_client_roles():
    claims = TokenClaims.model_validate(
        {
            "sub": SUB,
            "preferred_username": "coach",
            "realm_access": {"roles": ["coach"]},
            "resource_access": {
                "crossfit": {"roles": ["extra"]},
                "other": {"roles": ["ignored"]},
            },
            "email": "unused@example.com",
        }
    )
    user = claims.to_user("crossfit")
    assert user.user_id == UUID(SUB)
    assert user.roles == {"coach", "extra"}
    assert claims.to_user().roles == {"coach"}


# --- require_role -----------------------------------------------------------------


def make_role_app(*required: str, user_roles: set[str]) -> FastAPI:
    role_app = FastAPI()
    register_error_handlers(role_app)

    @role_app.get("/protected")
    async def protected(
        user: Annotated[AuthUser, Depends(require_role(*required))],
    ) -> dict:
        return {"user_id": str(user.user_id)}

    role_app.dependency_overrides[get_current_user] = lambda: AuthUser(
        user_id=uuid4(), roles=frozenset(user_roles)
    )
    return role_app


@pytest.mark.parametrize(
    ("required", "user_roles", "expected"),
    [
        (("trainer",), {"trainer"}, 200),
        (("trainer",), {"trainee"}, 403),
        (("trainer", "admin"), {"admin"}, 200),  # any of the roles is enough
        (("trainer",), set(), 403),
        ((), {"trainer"}, 403),  # no roles configured: fails closed
    ],
)
async def test_require_role(required, user_roles, expected):
    role_app = make_role_app(*required, user_roles=user_roles)
    async with AsyncClient(
        transport=ASGITransport(app=role_app), base_url="http://t"
    ) as c:
        response = await c.get("/protected")
    assert response.status_code == expected
    if expected == 403:
        assert response.json() == {"detail": "Insufficient permissions"}
