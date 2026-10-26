"""CORS tests without a database."""

import pytest
from httpx import ASGITransport, AsyncClient

from crosfit_training_backend.main import app
from crosfit_training_backend.settings import get_settings

FRONTEND = "http://localhost:4200"


@pytest.fixture
async def anon():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


def test_default_origin_is_the_frontend_from_the_keycloak_realm():
    assert FRONTEND in get_settings().CORS_ORIGINS


async def test_preflight_from_the_frontend_is_allowed(anon):
    response = await anon.options(
        "/trainings",
        headers={
            "Origin": FRONTEND,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed and "content-type" in allowed
    for method in ("PUT", "PATCH", "DELETE"):
        assert method in response.headers["access-control-allow-methods"]


async def test_preflight_from_unknown_origin_is_rejected(anon):
    response = await anon.options(
        "/trainings",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


async def test_error_responses_carry_cors_headers(anon):
    # without the header the browser would hide the real 401/403 behind a CORS error
    response = await anon.get("/me", headers={"Origin": FRONTEND})
    assert response.status_code in (401, 403)
    assert response.headers["access-control-allow-origin"] == FRONTEND


async def test_unknown_origin_gets_no_cors_headers(anon):
    response = await anon.get("/me", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_origins_come_from_the_environment(monkeypatch):
    from crosfit_training_backend import settings

    monkeypatch.setattr(settings, "_settings", None)
    monkeypatch.setenv("CORS_ORIGINS", " https://a.example , https://b.example,, ")
    assert settings.get_settings().CORS_ORIGINS == (
        "https://a.example",
        "https://b.example",
    )
    monkeypatch.setattr(settings, "_settings", None)  # do not leak into other tests
