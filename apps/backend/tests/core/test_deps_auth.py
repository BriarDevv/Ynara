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

import asyncio
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


# ---------- blocklist de jti en get_current_claims (issue #142, item 7) ----------


def test_revoked_jti_returns_401(client: TestClient) -> None:
    """Un access cuyo jti está blocklisteado -> 401 + WWW-Authenticate: Bearer.

    Mintea un access con un jti conocido, lo pre-revoca en un InMemoryTokenStore y
    overridea get_token_store con ESE store (no el vacío del autouse). El
    get_current_claims debe rechazar el token revocado aunque la firma/exp valguen.
    """
    uid = uuid.uuid4()
    token = create_access_token(str(uid), jti="fixed-jti")
    store = InMemoryTokenStore()

    async def _seed() -> None:
        await store.revoke("fixed-jti", ttl_seconds=60)

    asyncio.run(_seed())
    _app.dependency_overrides[get_token_store] = lambda: store
    try:
        resp = client.get("/protected", headers=_bearer(token))
    finally:
        # Restaurar el override autouse (store vacío) para no contaminar otros tests.
        _app.dependency_overrides[get_token_store] = lambda: InMemoryTokenStore()
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_non_revoked_jti_with_nonempty_store_returns_200(client: TestClient) -> None:
    """Simétrico: un jti NO revocado con un store no-vacío -> 200 (fija el contrato).

    El store tiene OTRO jti blocklisteado, pero no el del token: el blocklist check
    solo rechaza el jti exacto, no cualquier token cuando el store tiene entradas.
    """
    uid = uuid.uuid4()
    token = create_access_token(str(uid), jti="otro-jti-vivo")
    store = InMemoryTokenStore()

    async def _seed() -> None:
        await store.revoke("jti-de-otro-token", ttl_seconds=60)

    asyncio.run(_seed())
    _app.dependency_overrides[get_token_store] = lambda: store
    try:
        resp = client.get("/protected", headers=_bearer(token))
    finally:
        _app.dependency_overrides[get_token_store] = lambda: InMemoryTokenStore()
    assert resp.status_code == 200
    assert resp.json()["user_id"] == str(uid)


# ---------- family-revocation por sid en get_current_claims (item 1 de #142) ----------


def test_family_revoked_jti_returns_401(client: TestClient) -> None:
    """Un access de una familia (sid) revocada -> 401 + WWW-Authenticate: Bearer.

    El test crítico: revocar la familia mata cualquier access hermano de esa sesión,
    no solo el refresh. Mintea un access con un sid conocido, pre-revoca esa familia
    en el store y verifica el 401 aunque la firma/exp/jti valgan.
    """
    uid = uuid.uuid4()
    token = create_access_token(str(uid), {"sid": "S"}, jti="jti-vivo")
    store = InMemoryTokenStore()

    async def _seed() -> None:
        await store.revoke_family("S", ttl_seconds=60)

    asyncio.run(_seed())
    _app.dependency_overrides[get_token_store] = lambda: store
    try:
        resp = client.get("/protected", headers=_bearer(token))
    finally:
        _app.dependency_overrides[get_token_store] = lambda: InMemoryTokenStore()
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_access_sin_sid_no_se_afecta_por_family(client: TestClient) -> None:
    """Compat: un access SIN sid no se ve afectado por familias revocadas (skip)."""
    uid = uuid.uuid4()
    token = create_access_token(str(uid), jti="jti-sin-sid")  # sin sid
    store = InMemoryTokenStore()

    async def _seed() -> None:
        await store.revoke_family("alguna-familia", ttl_seconds=60)

    asyncio.run(_seed())
    _app.dependency_overrides[get_token_store] = lambda: store
    try:
        resp = client.get("/protected", headers=_bearer(token))
    finally:
        _app.dependency_overrides[get_token_store] = lambda: InMemoryTokenStore()
    assert resp.status_code == 200
    assert resp.json()["user_id"] == str(uid)


def test_distinto_sid_no_afectado(client: TestClient) -> None:
    """Aislamiento: revocar la familia B no afecta un access de la familia A."""
    uid = uuid.uuid4()
    token = create_access_token(str(uid), {"sid": "A"}, jti="jti-A")
    store = InMemoryTokenStore()

    async def _seed() -> None:
        await store.revoke_family("B", ttl_seconds=60)  # otra familia

    asyncio.run(_seed())
    _app.dependency_overrides[get_token_store] = lambda: store
    try:
        resp = client.get("/protected", headers=_bearer(token))
    finally:
        _app.dependency_overrides[get_token_store] = lambda: InMemoryTokenStore()
    assert resp.status_code == 200
    assert resp.json()["user_id"] == str(uid)
