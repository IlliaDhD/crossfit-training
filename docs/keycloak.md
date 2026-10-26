# Keycloak authentication

The backend has no users collection. A user is identified only by the Keycloak
access token: `sub` becomes `user_id` in every document, and the roles come from the
token as well. Keycloak is responsible for login, passwords and roles.

## Keycloak settings the backend relies on

Everything below is already configured in `keycloak/realm-export.json`
(realm `crossfit`, imported by `docker compose up`).

| What | Value | Why |
|---|---|---|
| Realm | `crossfit` | Part of the issuer and JWKS URL |
| Client | `crossfit-frontend` (public, Authorization Code + PKCE `S256`) | Frontend logs users in |
| Realm roles | `coach`, `athlete` | Read from `realm_access.roles` |
| Audience mapper on the client | adds `crossfit-api` to the `aud` claim of the access token | The backend accepts only tokens meant for it |
| Signing algorithm | `RS256` (Keycloak default) | Keys are fetched from the realm JWKS |
| `directAccessGrantsEnabled` | `true` (**dev realm only**) | Lets you get a token with a simple HTTP call, see below |

The audience mapper is required: without it Keycloak issues `aud: ["account"]` and
the backend rejects every token. Roles of the client `KEYCLOAK_CLIENT_ID`
(`resource_access`) are merged with realm roles if you ever use client roles.

## What the backend checks

For every request with `Authorization: Bearer <token>`:

1. The signature, with the key from the realm JWKS (matched by `kid`). Only `RS256` is
   accepted, so `alg: none` and HMAC tricks do not work.
2. `exp` (not expired), `iss` (equals the realm URL), `aud` (contains
   `KEYCLOAK_AUDIENCE`). The claims `exp`, `iss`, `aud`, `sub` **must be present**;
   the JWT library does not require them by default.
3. `sub` is a UUID.

Signing keys are cached. When a token has an unknown `kid` (Keycloak rotated its keys)
the JWKS is downloaded again, at most once per 30 seconds.

| Situation | Response |
|---|---|
| No / invalid / expired token | `401` and `WWW-Authenticate: Bearer` |
| Valid token without the needed role | `403` |
| Keycloak is unreachable (no cached keys) | `503` |

## Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `KEYCLOAK_URL` | – | Base URL, e.g. `http://localhost:8080`. Must equal the `iss` host in tokens (`KC_HOSTNAME` in docker-compose) |
| `KEYCLOAK_REALM` | – | Realm name |
| `KEYCLOAK_CLIENT_ID` | – | Client whose roles are merged with realm roles |
| `KEYCLOAK_AUDIENCE` | `crossfit-api` | Required value in `aud` |
| `KEYCLOAK_ADMIN_ROLE_NAME` | – | Role allowed to change the exercise catalog. Empty = nobody |

## Using it in code

```python
from typing import Annotated
from fastapi import Depends
from crosfit_training_backend.api.dependencies import CurrentUser, require_role
from crosfit_training_backend.api.schemas.user import AuthUser

@router.get("/mine")
async def mine(user: CurrentUser):               # any logged-in user
    ...  # user.user_id (UUID, token `sub`), user.username, user.roles

@router.post("/programs")
async def create(user: Annotated[AuthUser, Depends(require_role("coach"))]):
    ...                                          # needs at least one of the roles
```

Role names are plain strings passed to `require_role`, so introducing new roles
(for example `trainer` / `trainee`) means: create the role in Keycloak, assign it to
users, and use `require_role("<name>")`. No other backend change is needed.

`GET /me` returns the user the token belongs to (`user_id`, `username`, `roles`).

## Local development

```powershell
cp .env.example .env
docker compose up -d                 # Keycloak on http://localhost:8080 (admin / admin)
cd backend
uv run uvicorn crosfit_training_backend.main:app --reload --env-file ../.env
```

Test users: `coach` / `coach123` and `athlete` / `athlete123`. Get a token and call the API:

```powershell
$token = (Invoke-RestMethod -Method Post `
  -Uri http://localhost:8080/realms/crossfit/protocol/openid-connect/token `
  -Body @{ client_id = "crossfit-frontend"; grant_type = "password"
           username = "coach"; password = "coach123" }).access_token

Invoke-RestMethod http://127.0.0.1:8000/me -Headers @{ Authorization = "Bearer $token" }
```

In Swagger (`/docs`) press **Authorize** and paste the token.

**Realm changes are not re-imported.** Keycloak imports `realm-export.json` only when
the realm does not exist yet, and the realm lives in the `keycloak_data` volume. After
editing the file run `docker compose down -v` and `docker compose up -d`
(this deletes every volume of the compose project).

Tokens are valid for a few minutes (Keycloak default 5 min), get a new one when you
receive `401`.

## Before production

Disable `directAccessGrantsEnabled`, set `sslRequired` to `external`, replace the
test users and the `admin` / `admin` bootstrap account, and set `KC_HOSTNAME` to the
public HTTPS URL (it must match `KEYCLOAK_URL`).
