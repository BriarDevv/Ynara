"""Tests de get_current_user / CurrentUser (deps.py).

Mini-app FastAPI + TestClient sincrónico (httpx transport).  No toca DB.
El JWT se mintea con create_access_token y se verifica con verify_access_token;
ambas leen get_settings().  Para que usen el mismo secret determinista,
parcheamos *ambas* rutas de importación:

  - app.core.security.get_settings  (usada por create_access_token / verify_access_token)
  - app.core.deps.get_settings      (usada en el módulo-level de deps.py para el engine;
                                     get_current_user llama a verify_access_token que ya
                                     usa el patch de security, así que este patch es
                                     precautorio pero no rompe nada)
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import CurrentUser, get_token_store
from app.core.security import create_access_token
from app.core.token_store import InMemoryTokenStore

# ---------- settings determinista ----------

_SECRET = "test-secret-no-usar-en-prod"
_ALG = "HS256"


def _make_settings(*, expire_minutes: int = 60) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET=_SECRET,
        JWT_ALGORITHM=_ALG,
        JWT_EXPIRE_MINUTES=expire_minutes,
    )


@pytest.fixture(autouse=True)
def patched_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Garantiza que create_access_token y verify_access_token usen el mismo secret."""
    s = _make_settings()
    monkeypatch.setattr("app.core.security.get_settings", lambda: s)
    return s


# ---------- mini-app de prueba ----------

_app = FastAPI()


@_app.get("/protected")
async def _protected(user_id: CurrentUser) -> dict:
    return {"user_id": str(user_id)}


# get_current_user ahora chequea la blocklist vía get_token_store (issue #63);
# la mini-app no monta app.state.token_store, así que overrideamos la dep con un
# InMemoryTokenStore vacío (nada blocklisteado): los tests de validez del JWT no
# cambian de comportamiento.
_app.dependency_overrides[get_token_store] = lambda: InMemoryTokenStore()


@pytest.fixture
def client() -> TestClient:
    return TestClient(_app, raise_server_exceptions=True)


# ---------- helpers ----------


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------- casos ----------


def test_valid_token_returns_200_with_uuid(client: TestClient) -> None:
    uid = uuid.uuid4()
    token = create_access_token(str(uid))
    resp = client.get("/protected", headers=_bearer(token))
    assert resp.status_code == 200
    assert resp.json()["user_id"] == str(uid)


def test_no_auth_header_returns_401(client: TestClient) -> None:
    resp = client.get("/protected")
    assert resp.status_code == 401


def test_expired_token_returns_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Mintear con expiración -1 minuto usando un Settings con expire=-1.
    # jose permite exp en el pasado al encode; la verificación lo rechaza.
    from datetime import UTC, datetime, timedelta

    from jose import jwt as _jwt

    expired_token = _jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        _SECRET,
        algorithm=_ALG,
    )
    resp = client.get("/protected", headers=_bearer(expired_token))
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers


def test_sub_not_uuid_returns_401(client: TestClient) -> None:
    token = create_access_token("esto-no-es-un-uuid")
    resp = client.get("/protected", headers=_bearer(token))
    assert resp.status_code == 401


def test_tampered_token_returns_401(client: TestClient) -> None:
    token = create_access_token(str(uuid.uuid4()))
    tampered = token[:-3] + "xxx"
    resp = client.get("/protected", headers=_bearer(tampered))
    assert resp.status_code == 401


def test_www_authenticate_header_present_on_401(client: TestClient) -> None:
    resp = client.get("/protected")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"
