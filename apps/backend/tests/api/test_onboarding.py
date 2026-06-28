"""Tests E2E de ``POST /v1/onboarding`` (intake operativo del onboarding, ADR-026).

``integration`` (tocan la DB de tests dedicada vía ``db_session``): el endpoint
COMMITEA, así que el patrón es el de ``test_users.py`` — el savepoint del fixture
revierte todo al final. Auth con un JWT real (``create_access_token``) para el
``user_id`` sembrado; el ``InMemoryTokenStore`` del conftest cubre la blocklist.

Cubre:
1. POST con intake válido → 200; ``preferences`` con ``interested_modes`` + ``a11y``;
   ``onboarding_completed=True``; ``display_name`` seteado; persiste en la fila; sin
   ``password_hash``.
2. POST sin token → 401.
3. Modo inválido en ``interested_modes`` → 422.
4. ``interested_modes`` vacío (min_length 1) → 422.
5. Idempotencia: dos POST seguidos → el segundo PISA ``preferences`` + ``display_name``.
6. User inexistente (token válido, sin fila) → 401.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_embedder, get_reranker
from app.core.security import create_access_token
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.reranker import FakeReranker
from app.main import app
from app.models.user import User

pytestmark = pytest.mark.integration


def _valid_intake(**overrides: object) -> dict[str, object]:
    """Body válido del intake; ``overrides`` pisa claves puntuales por test."""
    body: dict[str, object] = {
        "display_name": "Mateo",
        "interested_modes": ["productividad", "estudio"],
        "a11y": {"text_size": "md", "high_contrast": False, "motion": "auto"},
        "mood": ["tranqui"],
        "mood_free_text": "arrancando el dia",
        "about": {
            "dedication": "ambos",
            "study_what": "ingenieria",
            "work_what": "freelance",
            "purpose": "organizarme",
            "interests": "musica, running",
        },
    }
    body.update(overrides)
    return body


async def _seed_user(session: AsyncSession, **fields: object) -> User:
    """Inserta un User (flush, sin commit) para que tenga id y sea visible."""
    user = User(**fields)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    """Header Authorization con un JWT válido para ``user_id``."""
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession) -> httpx.AsyncClient:
    """Cliente con ``get_db`` + clientes Fake overrideados, y el ``db_session`` del fixture.

    El endpoint depende de ``get_embedder``/``get_reranker`` (G4 siembra memoria
    semántica). Bajo ``ASGITransport`` el lifespan no corre, así que ``app.state`` no
    tiene esos singletons: se overridean con Fakes (espejo de ``test_memory_audit.py``).
    El caller usa el cliente dentro de ``async with`` y limpia los overrides en su
    ``finally`` con ``app.dependency_overrides.clear()``.
    """

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_embedder] = lambda: FakeEmbeddingClient()
    app.dependency_overrides[get_reranker] = lambda: FakeReranker()
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_onboarding_persists_operational_prefs(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/onboarding",
                headers=_bearer(user.id),
                json=_valid_intake(),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["display_name"] == "Mateo"
        assert body["onboarding_completed"] is True
        assert body["preferences"]["interested_modes"] == ["productividad", "estudio"]
        assert body["preferences"]["a11y"] == {
            "text_size": "md",
            "high_contrast": False,
            "motion": "auto",
        }
        assert "password_hash" not in body  # regla #4

        # Persistió en la fila (mismo session overrideado).
        await db_session.refresh(user)
        assert user.display_name == "Mateo"
        assert user.onboarding_completed is True
        assert user.preferences["interested_modes"] == ["productividad", "estudio"]
        assert user.preferences["a11y"]["text_size"] == "md"
    finally:
        app.dependency_overrides.clear()


async def test_onboarding_does_not_persist_memory_bound_signals(db_session: AsyncSession) -> None:
    # mood/about van a MEMORIA (G4), no a ``users.preferences``: solo lo operativo
    # (interested_modes + a11y) aterriza en ``preferences``. El seed de memoria se
    # cubre en ``test_onboarding_memory_seed.py``.
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/onboarding",
                headers=_bearer(user.id),
                json=_valid_intake(),
            )

        assert resp.status_code == 200
        await db_session.refresh(user)
        assert set(user.preferences.keys()) == {"interested_modes", "a11y"}
        assert "mood" not in user.preferences
        assert "about" not in user.preferences
    finally:
        app.dependency_overrides.clear()


async def test_onboarding_minimal_body_without_optionals(db_session: AsyncSession) -> None:
    # ``mood`` default ``[]``, ``mood_free_text``/``about`` opcionales: el mínimo es
    # ``display_name`` + ``interested_modes`` (≥1) + ``a11y``.
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/onboarding",
                headers=_bearer(user.id),
                json={
                    "display_name": "Ana",
                    "interested_modes": ["bienestar"],
                    "a11y": {"text_size": "lg", "high_contrast": True, "motion": "reduce"},
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["onboarding_completed"] is True
        assert body["preferences"]["interested_modes"] == ["bienestar"]
    finally:
        app.dependency_overrides.clear()


async def test_onboarding_requires_auth(db_session: AsyncSession) -> None:
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post("/v1/onboarding", json=_valid_intake())
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


async def test_onboarding_rejects_invalid_mode(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/onboarding",
                headers=_bearer(user.id),
                json=_valid_intake(interested_modes=["productividad", "nope"]),
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


async def test_onboarding_rejects_empty_modes(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/onboarding",
                headers=_bearer(user.id),
                json=_valid_intake(interested_modes=[]),
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


async def test_onboarding_is_idempotent(db_session: AsyncSession) -> None:
    # Re-llamar (re-onboarding) PISA ``preferences`` + ``display_name`` (upsert natural).
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            first = await client.post(
                "/v1/onboarding",
                headers=_bearer(user.id),
                json=_valid_intake(),
            )
            assert first.status_code == 200

            second = await client.post(
                "/v1/onboarding",
                headers=_bearer(user.id),
                json=_valid_intake(
                    display_name="Mateo G",
                    interested_modes=["vida"],
                    a11y={"text_size": "sm", "high_contrast": True, "motion": "normal"},
                ),
            )

        assert second.status_code == 200
        body = second.json()
        assert body["display_name"] == "Mateo G"
        assert body["preferences"]["interested_modes"] == ["vida"]
        assert body["preferences"]["a11y"]["text_size"] == "sm"

        # El segundo POST pisó la fila.
        await db_session.refresh(user)
        assert user.display_name == "Mateo G"
        assert user.preferences["interested_modes"] == ["vida"]
    finally:
        app.dependency_overrides.clear()


async def test_onboarding_unknown_user_returns_401(db_session: AsyncSession) -> None:
    # Token VÁLIDO para un user_id SIN fila (identidad propia caduca) → 401 (no 404),
    # mismo criterio que /auth/me y PATCH /users/me. No se siembra el user.
    ghost_id = uuid.uuid4()
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/onboarding",
                headers=_bearer(ghost_id),
                json=_valid_intake(),
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
