"""Tests E2E del módulo ``/v1/auth`` (register + login).

Todos son ``integration`` (tocan la DB de tests dedicada: ``register`` hace
``session.commit()``). Espejan el patrón de ``tests/api/test_chat.py``:

- ``httpx.AsyncClient`` + ``ASGITransport(app=app)`` golpea la app real.
- ``app.dependency_overrides[get_db]`` cede el ``db_session`` del fixture, así
  los asserts (y la limpieza) ven la MISMA sesión que commitea el endpoint.
- Cada test borra en ``finally`` el/los ``User`` que sembró
  (``_delete_user``, idempotente) para dejar la DB de tests limpia: el rollback
  del fixture NO alcanza para lo que el endpoint ya commiteó.

Cubre: 201 happy path + no-leak de hash, 409 duplicado, 409 por normalización,
422 (password corto / email inválido), 200 login + token decodificable, 401
password incorrecto, 401 email inexistente (anti-enumeración byte-a-byte contra
el camino password-incorrecto), 401 usuario sin password_hash (efímero), token
usable contra una ruta protegida real, y no-leak del password en errores.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_embedder, get_llm_client, get_reranker
from app.core.security import verify_access_token
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.reranker import FakeReranker
from app.llm.schemas import CompletionResult
from app.main import app
from app.models.user import User
from app.services.auth import _DUMMY_HASH, _normalize_email, authenticate_user

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _delete_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Borra el User sembrado (CASCADE arrastra lo dependiente). Idempotente."""
    await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(user_id)})
    await session.commit()


async def _delete_user_by_email(session: AsyncSession, email: str) -> None:
    """Borra por email normalizado (para tests que no capturan el id). Idempotente."""
    await session.execute(
        text("DELETE FROM users WHERE email = :email"), {"email": _normalize_email(email)}
    )
    await session.commit()


async def _client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """Overridea ``get_db`` con el ``db_session`` del fixture y devuelve un AsyncClient ASGI.

    El caller usa el cliente dentro de ``async with`` y limpia los overrides en
    su ``finally`` vía ``app.dependency_overrides.clear()``.
    """

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _override_chat_fakes(llm_client: FakeLlmClient) -> None:
    """Overridea las deps LLM/embedder/reranker con Fakes (para la ruta protegida)."""
    app.dependency_overrides[get_llm_client] = lambda: llm_client
    app.dependency_overrides[get_embedder] = FakeEmbeddingClient
    app.dependency_overrides[get_reranker] = FakeReranker


# ---------------------------------------------------------------------------
# 1. register 201 + no-leak de hash en la respuesta
# ---------------------------------------------------------------------------


async def test_register_201(db_session: AsyncSession) -> None:
    """201 + body UserOut con id/email(normalizado)/created_at; sin password ni hash."""
    email = "Nuevo.User@Example.com"
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/auth/register",
                json={"email": email, "password": "supersecreta1", "display_name": "Nuevo"},
            )
        assert resp.status_code == 201
        body = resp.json()
        # UserOut: id (UUID), email normalizado lower, timestamps.
        uuid.UUID(body["id"])
        assert body["email"] == "nuevo.user@example.com"
        assert "created_at" in body
        assert "updated_at" in body
        assert body["display_name"] == "Nuevo"
        # Regla #4: ni el password ni el hash viajan en la respuesta.
        assert "password" not in body
        assert "password_hash" not in body
        assert "supersecreta1" not in resp.text
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 2. register email duplicado -> 409
# ---------------------------------------------------------------------------


async def test_register_email_duplicado_409(db_session: AsyncSession) -> None:
    """Registrar dos veces el mismo email -> el segundo da 409."""
    email = "dup@example.com"
    client = await _client(db_session)
    try:
        async with client:
            first = await client.post(
                "/v1/auth/register",
                json={"email": email, "password": "supersecreta1"},
            )
            assert first.status_code == 201
            second = await client.post(
                "/v1/auth/register",
                json={"email": email, "password": "otrapass12345"},
            )
        assert second.status_code == 409
        assert second.json()["detail"] == "email ya registrado"
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 3. register normaliza email (strip + lower colapsa el duplicado) -> 409
# ---------------------------------------------------------------------------


async def test_register_normaliza_email_409(db_session: AsyncSession) -> None:
    """Registrar 'A@X.com' y luego '  a@x.com ' -> 409 (la normalización los colapsa)."""
    client = await _client(db_session)
    try:
        async with client:
            first = await client.post(
                "/v1/auth/register",
                json={"email": "A@X.com", "password": "supersecreta1"},
            )
            assert first.status_code == 201
            # Mismo email con mayúsculas + espacios: debe colapsar al mismo registro.
            second = await client.post(
                "/v1/auth/register",
                json={"email": "  a@x.com ", "password": "otrapass12345"},
            )
        assert second.status_code == 409
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, "a@x.com")


# ---------------------------------------------------------------------------
# 4. register password corto (7 chars) -> 422
# ---------------------------------------------------------------------------


async def test_register_password_corto_422(db_session: AsyncSession) -> None:
    """Password de 7 chars (< min_length 8) -> 422."""
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/auth/register",
                json={"email": "corto@example.com", "password": "7chars!"},
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()
        # Defensivo: no debería haberse creado, pero limpiamos por las dudas.
        await _delete_user_by_email(db_session, "corto@example.com")


# ---------------------------------------------------------------------------
# 5. register email inválido -> 422
# ---------------------------------------------------------------------------


async def test_register_email_invalido_422(db_session: AsyncSession) -> None:
    """Email malformado -> 422 (EmailStr lo rechaza)."""
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/auth/register",
                json={"email": "no-es-un-email", "password": "supersecreta1"},
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. login OK -> 200 + TokenOut, token decodificable con sub == user.id
# ---------------------------------------------------------------------------


async def test_token_login_ok_200(db_session: AsyncSession) -> None:
    """Registrar y luego /token -> 200; token_type bearer; sub == str(user.id)."""
    email = "login.ok@example.com"
    password = "supersecreta1"
    client = await _client(db_session)
    try:
        async with client:
            reg = await client.post(
                "/v1/auth/register",
                json={"email": email, "password": password},
            )
            assert reg.status_code == 201
            user_id = reg.json()["id"]

            resp = await client.post(
                "/v1/auth/token",
                json={"email": email, "password": password},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        access_token = body["access_token"]
        # El token decodifica y su sub es el id del usuario registrado.
        payload = verify_access_token(access_token)
        assert payload["sub"] == str(user_id)
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 7. login password incorrecto -> 401 con WWW-Authenticate: Bearer
# ---------------------------------------------------------------------------


async def test_token_password_incorrecto_401(db_session: AsyncSession) -> None:
    """User existe, password mal -> 401 con header WWW-Authenticate: Bearer."""
    email = "wrong.pass@example.com"
    client = await _client(db_session)
    try:
        async with client:
            reg = await client.post(
                "/v1/auth/register",
                json={"email": email, "password": "supersecreta1"},
            )
            assert reg.status_code == 201
            resp = await client.post(
                "/v1/auth/token",
                json={"email": email, "password": "password-incorrecto"},
            )
        assert resp.status_code == 401
        assert resp.headers.get("WWW-Authenticate") == "Bearer"
        assert resp.json()["detail"] == "credenciales invalidas"
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 8. login email inexistente -> 401 IDÉNTICO al de password incorrecto
#    (assert anti-enumeración: mismo status + body + headers relevantes)
# ---------------------------------------------------------------------------


async def test_token_email_inexistente_401(db_session: AsyncSession) -> None:
    """Email inexistente y password incorrecto deben dar el MISMO 401 (anti-enum)."""
    existing_email = "exists@example.com"
    client = await _client(db_session)
    try:
        async with client:
            reg = await client.post(
                "/v1/auth/register",
                json={"email": existing_email, "password": "supersecreta1"},
            )
            assert reg.status_code == 201

            # Camino A: email existe, password incorrecto.
            wrong_pass = await client.post(
                "/v1/auth/token",
                json={"email": existing_email, "password": "password-incorrecto"},
            )
            # Camino B: email que no existe.
            unknown_email = await client.post(
                "/v1/auth/token",
                json={"email": "no.existe@example.com", "password": "loquesea12345"},
            )

        # Anti-enumeración: ambos caminos son indistinguibles para el atacante.
        assert wrong_pass.status_code == 401
        assert unknown_email.status_code == 401
        assert wrong_pass.json() == unknown_email.json()
        assert (
            wrong_pass.headers.get("WWW-Authenticate")
            == unknown_email.headers.get("WWW-Authenticate")
            == "Bearer"
        )
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, existing_email)


# ---------------------------------------------------------------------------
# 9. login de usuario sin password_hash (efímero) -> 401 (no rompe verify_password)
# ---------------------------------------------------------------------------


async def test_token_usuario_sin_password_hash_401(db_session: AsyncSession) -> None:
    """User con password_hash=None (efímero) -> /token da 401, sin tronar."""
    email = "ephemeral@example.com"
    # Sembrar directo vía el fixture: usuario con email pero sin hash.
    user = User(email=_normalize_email(email), password_hash=None, is_ephemeral=True)
    db_session.add(user)
    await db_session.commit()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/auth/token",
                json={"email": email, "password": "cualquiercosa12345"},
            )
        assert resp.status_code == 401
        assert resp.headers.get("WWW-Authenticate") == "Bearer"
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# 10. token minteado por /token sirve contra una ruta protegida real (E2E loop)
# ---------------------------------------------------------------------------


async def test_token_usable_contra_ruta_protegida(db_session: AsyncSession) -> None:
    """El token de /token autentica contra POST /v1/chat (ruta con CurrentUser)."""
    email = "e2e.loop@example.com"
    password = "supersecreta1"
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(
        CompletionResult(
            text="hola",
            finish_reason="stop",
            tool_calls=[],
            prompt_tokens=10,
            completion_tokens=5,
            model_name="gemma4",
            latency_ms=42.0,
        )
    )
    client = await _client(db_session)
    _override_chat_fakes(fake)
    user_id: uuid.UUID | None = None
    try:
        async with client:
            reg = await client.post(
                "/v1/auth/register",
                json={"email": email, "password": password},
            )
            assert reg.status_code == 201
            user_id = uuid.UUID(reg.json()["id"])

            tok = await client.post(
                "/v1/auth/token",
                json={"email": email, "password": password},
            )
            assert tok.status_code == 200
            access_token = tok.json()["access_token"]

            # Usar el token contra una ruta protegida real: NO debe dar 401.
            protected = await client.post(
                "/v1/chat",
                json={"text": "hola", "mode": "vida"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        assert protected.status_code == 200
        assert protected.status_code != 401
    finally:
        app.dependency_overrides.clear()
        if user_id is not None:
            await _delete_user(db_session, user_id)


# ---------------------------------------------------------------------------
# 11. no-leak del password en errores (422 de register y 401 de login)
# ---------------------------------------------------------------------------


async def test_no_leak_password_en_errores(db_session: AsyncSession) -> None:
    """El password enviado NO aparece en el response.text del 422 ni del 401."""
    leak_marker = "Sup3rSecretLeakMarker"
    client = await _client(db_session)
    try:
        async with client:
            # 422: password corto -> el eco del input de Pydantic debe estar scrubbeado.
            short_pwd = leak_marker[:7]
            r422 = await client.post(
                "/v1/auth/register",
                json={"email": "leak422@example.com", "password": short_pwd},
            )
            assert r422.status_code == 422
            assert short_pwd not in r422.text

            # Registrar un user válido para ejercitar el 401 con password incorrecto.
            reg = await client.post(
                "/v1/auth/register",
                json={"email": "leak401@example.com", "password": "supersecreta1"},
            )
            assert reg.status_code == 201

            # 401: el password (incorrecto) enviado no debe aparecer en la respuesta.
            r401 = await client.post(
                "/v1/auth/token",
                json={"email": "leak401@example.com", "password": leak_marker},
            )
            assert r401.status_code == 401
            assert leak_marker not in r401.text
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, "leak422@example.com")
        await _delete_user_by_email(db_session, "leak401@example.com")


# ---------------------------------------------------------------------------
# Unit (opcional): normalización + dummy hash en el camino "usuario inexistente"
# ---------------------------------------------------------------------------


def test_normalize_email_unit() -> None:
    """_normalize_email hace trim + lower de forma idempotente."""
    assert _normalize_email("  A@X.COM ") == "a@x.com"
    assert _normalize_email("a@x.com") == "a@x.com"


async def test_authenticate_user_inexistente_corre_dummy_hash(
    db_session: AsyncSession,
) -> None:
    """authenticate_user con email inexistente devuelve None y corre el dummy hash."""
    from unittest.mock import patch

    import app.services.auth as auth_service

    with patch.object(
        auth_service, "verify_password", wraps=auth_service.verify_password
    ) as spy:
        result = await authenticate_user(
            db_session, email="seguro.no.existe@example.com", password="loquesea12345"
        )
    assert result is None
    # Timing-safe: se corrió verify_password contra el dummy hash precomputado.
    spy.assert_called_once_with("loquesea12345", _DUMMY_HASH)
