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

from app.core.deps import get_db, get_embedder, get_llm_client, get_reranker, get_token_store
from app.core.security import create_access_token, verify_access_token, verify_token
from app.core.token_store import InMemoryTokenStore, TokenStore
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


async def _client(
    db_session: AsyncSession, *, store: TokenStore | None = None
) -> httpx.AsyncClient:
    """Overridea ``get_db`` + ``get_token_store`` y devuelve un AsyncClient ASGI.

    ``store`` (issue #63): el ``TokenStore`` que la blocklist + rate-limit usan.
    Por default un ``InMemoryTokenStore`` fresco (sin Redis); los tests que
    necesitan inspeccionar/forzar el store pasan el suyo. El caller usa el cliente
    dentro de ``async with`` y limpia los overrides en su ``finally`` vía
    ``app.dependency_overrides.clear()``.
    """

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    resolved_store = store if store is not None else InMemoryTokenStore()
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_token_store] = lambda: resolved_store
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
# 12. GET /auth/me → 200 con el UserOut del user logueado (sin password_hash)
# ---------------------------------------------------------------------------


async def test_me_returns_own_user(db_session: AsyncSession) -> None:
    """register → token → GET /auth/me: 200 con email correcto y sin password_hash."""
    email = "me.ok@example.com"
    password = "supersecreta1"
    client = await _client(db_session)
    try:
        async with client:
            reg = await client.post(
                "/v1/auth/register",
                json={"email": email, "password": password, "display_name": "Yo"},
            )
            assert reg.status_code == 201
            user_id = reg.json()["id"]

            tok = await client.post(
                "/v1/auth/token",
                json={"email": email, "password": password},
            )
            assert tok.status_code == 200
            access_token = tok.json()["access_token"]

            resp = await client.get(
                "/v1/auth/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        assert resp.status_code == 200
        body = resp.json()
        # Es la identidad del user logueado.
        assert body["id"] == user_id
        assert body["email"] == "me.ok@example.com"
        assert body["display_name"] == "Yo"
        assert "created_at" in body
        assert "updated_at" in body
        # Regla #4: el hash de password NUNCA viaja (no es campo de UserOut).
        assert "password_hash" not in body
        assert "password" not in body
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 13. GET /auth/me con token de un user inexistente (borrado) → 401 (no 404)
# ---------------------------------------------------------------------------


async def test_me_token_de_user_inexistente_401(db_session: AsyncSession) -> None:
    """Token válido cuyo sub no tiene fila (user borrado) → 401, NO 404.

    Es la PROPIA identidad caduca, no un recurso ajeno: se responde 401 con
    WWW-Authenticate: Bearer (re-autenticarse), no un 404 de recurso ausente.
    """
    # Token bien firmado para un id que NUNCA existió en la DB.
    ghost_id = uuid.uuid4()
    token = create_access_token(str(ghost_id))

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(
                "/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 401
        assert resp.status_code != 404
        assert resp.headers.get("WWW-Authenticate") == "Bearer"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 14. GET /auth/me sin token → 401
# ---------------------------------------------------------------------------


async def test_me_sin_token_401(db_session: AsyncSession) -> None:
    """Sin Authorization header → 401 (get_current_user, auto_error)."""
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/auth/me")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


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

    with patch.object(auth_service, "verify_password", wraps=auth_service.verify_password) as spy:
        result = await authenticate_user(
            db_session, email="seguro.no.existe@example.com", password="loquesea12345"
        )
    assert result is None
    # Timing-safe: se corrió verify_password contra el dummy hash precomputado.
    spy.assert_called_once_with("loquesea12345", _DUMMY_HASH)


# ===========================================================================
# Issue #63 — refresh, blocklist/logout, rate-limit, higiene
# ===========================================================================


async def _register_and_login(
    client: httpx.AsyncClient, *, email: str, password: str
) -> tuple[str, str, str]:
    """Helper: register + token. Devuelve (user_id, access_token, refresh_token)."""
    reg = await client.post("/v1/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 201
    user_id = reg.json()["id"]
    tok = await client.post("/v1/auth/token", json={"email": email, "password": password})
    assert tok.status_code == 200
    body = tok.json()
    return user_id, body["access_token"], body["refresh_token"]


# ---------------------------------------------------------------------------
# 18. /token devuelve refresh_token + access_token (TokenOut extendido)
# ---------------------------------------------------------------------------


async def test_token_devuelve_refresh(db_session: AsyncSession) -> None:
    """/token ahora trae refresh_token no-nulo además del access_token."""
    email = "refresh.issue@example.com"
    client = await _client(db_session)
    try:
        async with client:
            _, access, refresh = await _register_and_login(
                client, email=email, password="supersecreta1"
            )
        assert access
        assert refresh
        # access y refresh son tokens distintos.
        assert access != refresh
        # El access sigue siendo un access válido (sub presente).
        assert verify_access_token(access)["sub"]
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 19. Backward-compat: el access de /token sigue autenticando /me
# ---------------------------------------------------------------------------


async def test_access_token_sigue_autenticando_me(db_session: AsyncSession) -> None:
    """El access_token de /token autentica /auth/me (contrato access-only intacto)."""
    email = "compat.me@example.com"
    client = await _client(db_session)
    try:
        async with client:
            _, access, _ = await _register_and_login(client, email=email, password="supersecreta1")
            me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert me.status_code == 200
        assert me.json()["email"] == email
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 20. /auth/refresh con refresh válido -> 200 + nuevo access autentica /me
# ---------------------------------------------------------------------------


async def test_refresh_ok_emite_nuevos_tokens(db_session: AsyncSession) -> None:
    """/refresh con refresh válido -> 200, nuevo access + refresh; el nuevo access vale."""
    email = "refresh.ok@example.com"
    client = await _client(db_session)
    try:
        async with client:
            _, _, refresh = await _register_and_login(client, email=email, password="supersecreta1")
            resp = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
            assert resp.status_code == 200
            body = resp.json()
            new_access = body["access_token"]
            new_refresh = body["refresh_token"]
            assert new_access and new_refresh
            assert new_refresh != refresh  # rotó
            me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {new_access}"})
        assert me.status_code == 200
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 21. Rotación con reuse-detection a nivel familia (item 1 de #142).
#
#  Residual #3 del SPEC: con la ventana de gracia retry-safe, un reuse INMEDIATO
#  del refresh recién rotado es indistinguible de un retry de red benigno -> 200
#  re-minteado (NO 401), y la familia NO queda revocada. El 401 + family-revoke
#  aparece cuando el reuse llega FUERA del grace (test 21b, con advance()).
# ---------------------------------------------------------------------------


async def test_refresh_reuse_inmediato_es_retry_safe(db_session: AsyncSession) -> None:
    """Reuse inmediato (dentro del grace) -> 200 re-minteado; la familia NO se nukea.

    Antes (item 3) este reuse daba 401. Con el grace window retry-safe, un reenvío
    del mismo refresh dentro de los 30s es un retry benigno (no se puede distinguir
    de un robo en esa ventana — concesión consciente, residual #3). El cliente
    recibe un par usable y un access hermano sigue dando 200.
    """
    email = "refresh.retry@example.com"
    store = InMemoryTokenStore()
    client = await _client(db_session, store=store)
    try:
        async with client:
            _, access, refresh = await _register_and_login(
                client, email=email, password="supersecreta1"
            )
            first = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
            assert first.status_code == 200
            # Reuse inmediato (dentro del grace): retry benigno -> 200 re-minteado.
            retry = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
            assert retry.status_code == 200
            assert retry.json()["access_token"]
            # La familia NO fue revocada: el access ORIGINAL del login sigue vivo.
            me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert me.status_code == 200
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


async def test_refresh_retry_converge_en_el_sucesor(db_session: AsyncSession) -> None:
    """El retry benigno reusa el jti del sucesor canónico (anti-fork de familia).

    La rama 1 (first-use) mintea un sucesor con jti ``J1`` y deja el grace marker
    ``old_jti -> J1``. Un reuse dentro del grace (rama 2) debe converger en ESE
    mismo ``J1``, no mintear una cadena paralela con jti random: si forkeara, las
    dos cadenas rotarían independientes y jamás dispararían la reuse-detection (el
    robo escaparía hasta el exp natural, 30d). Convergiendo en un único sucesor, un
    reuse posterior fuera de grace vuelve a caer en breach y la familia se mata.
    """
    email = "refresh.converge@example.com"
    store = InMemoryTokenStore()
    client = await _client(db_session, store=store)
    try:
        async with client:
            _, _, refresh = await _register_and_login(client, email=email, password="supersecreta1")
            first = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
            assert first.status_code == 200
            j1 = verify_token(first.json()["refresh_token"], expected_type="refresh")["jti"]
            # Reuse dentro del grace: el refresh re-emitido reusa EL MISMO sucesor.
            retry = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
            assert retry.status_code == 200
            j_retry = verify_token(retry.json()["refresh_token"], expected_type="refresh")["jti"]
            assert j_retry == j1  # converge en una sola cadena, no forkea la familia
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


async def test_refresh_reuse_fuera_del_grace_revoca_familia(
    db_session: AsyncSession,
) -> None:
    """Reuse FUERA del grace -> 401 y la familia QUEDA revocada (breach detectado).

    Inyecta un InMemoryTokenStore para avanzar el reloj más allá de la ventana de
    gracia (30s). Tras el advance, el grace marker expiró: el reuse del viejo ya no
    es un retry benigno sino replay/robo -> 401 + family-revoke. Un access hermano
    de esa familia pasa a 401.
    """
    email = "refresh.breach@example.com"
    store = InMemoryTokenStore()
    client = await _client(db_session, store=store)
    try:
        async with client:
            _, access, refresh = await _register_and_login(
                client, email=email, password="supersecreta1"
            )
            first = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
            assert first.status_code == 200
            # Pasar el grace (default 30s): el grace marker expira.
            store.advance(31)
            reuse = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
            assert reuse.status_code == 401
            # La familia quedó revocada: el access ORIGINAL hermano da 401.
            me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert me.status_code == 401
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 22. /auth/refresh con un ACCESS token (type mismatch) -> 401 uniforme
# ---------------------------------------------------------------------------


async def test_refresh_con_access_token_401(db_session: AsyncSession) -> None:
    """Mandar un access a /refresh (type mismatch) -> 401."""
    email = "refresh.mismatch@example.com"
    client = await _client(db_session)
    try:
        async with client:
            _, access, _ = await _register_and_login(client, email=email, password="supersecreta1")
            resp = await client.post("/v1/auth/refresh", json={"refresh_token": access})
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 23. /auth/refresh con token basura -> 401 y sin leak de PyJWT/token
# ---------------------------------------------------------------------------


async def test_refresh_token_basura_401_sin_leak(db_session: AsyncSession) -> None:
    """/refresh con firma mala -> 401; el response.text no filtra PyJWT ni el token."""
    client = await _client(db_session)
    try:
        async with client:
            garbage = "no-es-un-jwt-valido-12345"
            resp = await client.post("/v1/auth/refresh", json={"refresh_token": garbage})
        assert resp.status_code == 401
        # Regla #4: ni el token crudo ni el detalle de la lib JWT en la respuesta.
        assert garbage not in resp.text
        assert "jose" not in resp.text.lower()
        assert "pyjwt" not in resp.text.lower()
        assert "signature" not in resp.text.lower()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 24. Logout: el access actual -> 204; ese mismo access da 401 en /me
# ---------------------------------------------------------------------------


async def test_logout_blocklistea_access(db_session: AsyncSession) -> None:
    """/logout con el access actual -> 204; el MISMO access ahora da 401 en /me."""
    email = "logout.access@example.com"
    store = InMemoryTokenStore()
    client = await _client(db_session, store=store)
    try:
        async with client:
            _, access, _ = await _register_and_login(client, email=email, password="supersecreta1")
            # Antes del logout, el access vale.
            before = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
            assert before.status_code == 200
            out = await client.post(
                "/v1/auth/logout",
                json={},
                headers={"Authorization": f"Bearer {access}"},
            )
            assert out.status_code == 204
            # Tras el logout, el access quedó blocklisteado -> 401.
            after = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert after.status_code == 401
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 25. Logout con refresh en el body -> ese refresh luego da 401 en /refresh
# ---------------------------------------------------------------------------


async def test_logout_con_refresh_lo_revoca(db_session: AsyncSession) -> None:
    """Logout con refresh_token en el body -> ese refresh da 401 en /refresh después."""
    email = "logout.refresh@example.com"
    client = await _client(db_session)
    try:
        async with client:
            _, access, refresh = await _register_and_login(
                client, email=email, password="supersecreta1"
            )
            out = await client.post(
                "/v1/auth/logout",
                json={"refresh_token": refresh},
                headers={"Authorization": f"Bearer {access}"},
            )
            assert out.status_code == 204
            resp = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 26. Logout con refresh inválido en el body -> igual 204 (best-effort)
# ---------------------------------------------------------------------------


async def test_logout_con_refresh_invalido_204(db_session: AsyncSession) -> None:
    """Logout con refresh basura en el body -> 204 igual (idempotente, no rompe)."""
    email = "logout.badrefresh@example.com"
    client = await _client(db_session)
    try:
        async with client:
            _, access, _ = await _register_and_login(client, email=email, password="supersecreta1")
            out = await client.post(
                "/v1/auth/logout",
                json={"refresh_token": "basura-no-jwt"},
                headers={"Authorization": f"Bearer {access}"},
            )
        assert out.status_code == 204
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 27. Anti-enum del rate-limit: email existente vs inexistente -> 429 idéntico
# ---------------------------------------------------------------------------


async def test_rate_limit_anti_enum_429_identico(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N+1 fallos contra email existente y contra inexistente -> 429 byte-idéntico.

    Mismo número de intentos para llegar al lockout exista o no el email (el
    contador sube ante CUALQUIER user is None). El 429 es idéntico (status + body
    + Retry-After). No hay oráculo de enumeración.
    """
    # Threshold chico y determinista para el test.
    monkeypatch.setattr(
        "app.core.ratelimit.get_settings",
        lambda: _ratelimit_settings(max_attempts=2),
    )
    monkeypatch.setattr(
        "app.api.v1.auth.get_settings",
        lambda: _ratelimit_settings(max_attempts=2),
    )
    existing = "enum.existe@example.com"
    # Buckets distintos: cada email tiene su propio (ip, email_hash).
    client = await _client(db_session)
    try:
        async with client:
            reg = await client.post(
                "/v1/auth/register",
                json={"email": existing, "password": "supersecreta1"},
            )
            assert reg.status_code == 201

            # Camino A: email EXISTE, password mal. 2 fallos -> lockout -> 429.
            for _ in range(2):
                await client.post(
                    "/v1/auth/token",
                    json={"email": existing, "password": "mal-password"},
                )
            r_existing = await client.post(
                "/v1/auth/token",
                json={"email": existing, "password": "mal-password"},
            )

            # Camino B: email NO existe. Mismo número de intentos -> 429.
            nonexist = "enum.no.existe@example.com"
            for _ in range(2):
                await client.post(
                    "/v1/auth/token",
                    json={"email": nonexist, "password": "mal-password"},
                )
            r_nonexist = await client.post(
                "/v1/auth/token",
                json={"email": nonexist, "password": "mal-password"},
            )

        assert r_existing.status_code == 429
        assert r_nonexist.status_code == 429
        # Byte-idéntico: status + body + Retry-After.
        assert r_existing.json() == r_nonexist.json()
        assert r_existing.headers.get("Retry-After") == r_nonexist.headers.get("Retry-After")
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, existing)


# ---------------------------------------------------------------------------
# 28. Rate-limit no afecta el happy-path: login OK resetea el contador
# ---------------------------------------------------------------------------


async def test_login_ok_resetea_contador(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tras 2 fallos, un login OK limpia el bucket: no queda 'cerca' del lockout."""
    monkeypatch.setattr(
        "app.core.ratelimit.get_settings",
        lambda: _ratelimit_settings(max_attempts=3),
    )
    monkeypatch.setattr(
        "app.api.v1.auth.get_settings",
        lambda: _ratelimit_settings(max_attempts=3),
    )
    email = "reset.happy@example.com"
    password = "supersecreta1"
    client = await _client(db_session)
    try:
        async with client:
            reg = await client.post(
                "/v1/auth/register", json={"email": email, "password": password}
            )
            assert reg.status_code == 201
            # 2 fallos (threshold 3, todavía no lockea).
            for _ in range(2):
                bad = await client.post(
                    "/v1/auth/token",
                    json={"email": email, "password": "mal-password"},
                )
                assert bad.status_code == 401
            # Login OK: resetea el contador.
            ok = await client.post("/v1/auth/token", json={"email": email, "password": password})
            assert ok.status_code == 200
            # Otros 2 fallos: como el contador se reseteó, sigue sin lockear.
            for _ in range(2):
                again = await client.post(
                    "/v1/auth/token",
                    json={"email": email, "password": "mal-password"},
                )
                assert again.status_code == 401  # 401, no 429
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 29. Fail-open blocklist: store que lanza en is_revoked -> /me sigue 200
# ---------------------------------------------------------------------------


async def test_fail_open_blocklist(db_session: AsyncSession) -> None:
    """Con un store que lanza en is_revoked, /me con token válido sigue dando 200.

    El endpoint no asume que el store nunca falla: el RedisTokenStore atrapa y
    degrada, pero acá probamos que el HANDLER no rompe ante un store que lanza —
    debe degradar a fail-open. Para eso usamos el RedisTokenStore (que atrapa)
    envolviendo un cliente que tira.
    """
    from app.core.token_store import RedisTokenStore

    class _BoomRedisClient:
        async def exists(self, *a: object) -> int:
            raise RuntimeError("redis down")

        async def set(self, *a: object, **k: object) -> None:
            raise RuntimeError("redis down")

        async def incr(self, *a: object) -> int:
            raise RuntimeError("redis down")

        async def expire(self, *a: object, **k: object) -> None:
            raise RuntimeError("redis down")

        async def eval(self, *a: object, **k: object) -> int:
            raise RuntimeError("redis down")

        async def delete(self, *a: object) -> None:
            raise RuntimeError("redis down")

    email = "failopen.block@example.com"
    store = RedisTokenStore(_BoomRedisClient())
    client = await _client(db_session, store=store)
    try:
        async with client:
            _, access, _ = await _register_and_login(client, email=email, password="supersecreta1")
            me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
        # fail-open: Redis caído no convierte un token válido en 401/500.
        assert me.status_code == 200
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 30. Fail-open rate-limit: store que lanza -> /token con cred válidas sigue 200
# ---------------------------------------------------------------------------


async def test_fail_open_rate_limit(db_session: AsyncSession) -> None:
    """Con un store que lanza en las reads, /token con cred válidas sigue dando 200."""
    from app.core.token_store import RedisTokenStore

    class _BoomRedisClient:
        async def exists(self, *a: object) -> int:
            raise RuntimeError("redis down")

        async def set(self, *a: object, **k: object) -> None:
            raise RuntimeError("redis down")

        async def incr(self, *a: object) -> int:
            raise RuntimeError("redis down")

        async def expire(self, *a: object, **k: object) -> None:
            raise RuntimeError("redis down")

        async def eval(self, *a: object, **k: object) -> int:
            raise RuntimeError("redis down")

        async def delete(self, *a: object) -> None:
            raise RuntimeError("redis down")

    email = "failopen.rl@example.com"
    password = "supersecreta1"
    store = RedisTokenStore(_BoomRedisClient())
    # Sembrar el user con un store sano para el register, luego loguear con el boom.
    setup_client = await _client(db_session)
    try:
        async with setup_client:
            reg = await setup_client.post(
                "/v1/auth/register", json={"email": email, "password": password}
            )
            assert reg.status_code == 201
        app.dependency_overrides.clear()

        client = await _client(db_session, store=store)
        async with client:
            tok = await client.post("/v1/auth/token", json={"email": email, "password": password})
        # fail-open: Redis caído no bloquea el login con credenciales válidas.
        assert tok.status_code == 200
        assert tok.json()["access_token"]
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 31. Token viejo sin jti -> /me da 200 (se saltea el chequeo de blocklist)
# ---------------------------------------------------------------------------


async def test_token_viejo_sin_jti_me_200(db_session: AsyncSession) -> None:
    """Un access sin claim jti (pre-#63) autentica /me (se saltea el blocklist check)."""
    from datetime import UTC, datetime, timedelta

    import jwt

    from app.core.config import get_settings

    email = "legacy.nojti@example.com"
    client = await _client(db_session)
    try:
        async with client:
            reg = await client.post(
                "/v1/auth/register",
                json={"email": email, "password": "supersecreta1"},
            )
            assert reg.status_code == 201
            user_id = reg.json()["id"]
            # Mintear a mano un access SIN jti ni type (token pre-#63).
            settings = get_settings()
            legacy = jwt.encode(
                {
                    "sub": user_id,
                    "exp": datetime.now(UTC) + timedelta(hours=1),
                },
                settings.jwt_secret,
                algorithm=settings.jwt_algorithm,
            )
            me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {legacy}"})
        assert me.status_code == 200
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 32. /register rate-limit por IP -> 429 tras el threshold
# ---------------------------------------------------------------------------


async def test_register_rate_limit_429(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N+1 registros desde la misma IP -> 429; shape sin oráculo."""
    monkeypatch.setattr(
        "app.core.ratelimit.get_settings",
        lambda: _ratelimit_settings(register_max=2),
    )
    emails: list[str] = []
    client = await _client(db_session)
    try:
        async with client:
            # 2 registros permitidos (threshold 2).
            for i in range(2):
                e = f"rl.register.{i}@example.com"
                emails.append(e)
                r = await client.post(
                    "/v1/auth/register", json={"email": e, "password": "supersecreta1"}
                )
                assert r.status_code == 201
            # El 3ro cruza el límite por IP -> 429.
            e3 = "rl.register.3@example.com"
            emails.append(e3)
            r3 = await client.post(
                "/v1/auth/register", json={"email": e3, "password": "supersecreta1"}
            )
        assert r3.status_code == 429
        assert "demasiados" in r3.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        for e in emails:
            await _delete_user_by_email(db_session, e)


# ---------------------------------------------------------------------------
# 34. no-leak extendido: ni refresh ni access crudos en errores de los endpoints nuevos
# ---------------------------------------------------------------------------


async def test_no_leak_tokens_en_errores(db_session: AsyncSession) -> None:
    """Ni refresh ni access crudos aparecen en errores (422/401) de refresh/logout."""
    leak = "Leak3dTokenMarker12345"
    client = await _client(db_session)
    try:
        async with client:
            # 401 de /refresh con un token que lleva el marker (firma mala).
            r401 = await client.post("/v1/auth/refresh", json={"refresh_token": leak})
            assert r401.status_code == 401
            assert leak not in r401.text
            # 422 sobre el PROPIO campo refresh_token (tipo inválido: lista con el
            # marker dentro). El scrub de _SENSITIVE_VALIDATION_FIELDS debe ocultar
            # el eco del input del campo refresh_token (regla #4).
            r422 = await client.post("/v1/auth/refresh", json={"refresh_token": [leak]})
            assert r422.status_code == 422
            assert leak not in r422.text
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 35. Retry-After por endpoint (item 6 de #142): register usa su ventana, login su
#     lockout. Cada 429 informa cuánto esperar para SU límite, no un valor fijo.
# ---------------------------------------------------------------------------


async def test_retry_after_register_usa_window(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El 429 de /register trae Retry-After == auth_register_window_seconds."""
    monkeypatch.setattr(
        "app.core.ratelimit.get_settings",
        lambda: _ratelimit_settings(register_max=1),
    )
    monkeypatch.setattr(
        "app.api.v1.auth.get_settings",
        lambda: _ratelimit_settings(register_max=1),
    )
    emails: list[str] = []
    client = await _client(db_session)
    try:
        async with client:
            e0 = "retryafter.reg.0@example.com"
            emails.append(e0)
            ok = await client.post(
                "/v1/auth/register", json={"email": e0, "password": "supersecreta1"}
            )
            assert ok.status_code == 201
            e1 = "retryafter.reg.1@example.com"
            emails.append(e1)
            r429 = await client.post(
                "/v1/auth/register", json={"email": e1, "password": "supersecreta1"}
            )
        assert r429.status_code == 429
        # Retry-After == ventana del register (3600), no el lockout del login.
        assert r429.headers.get("Retry-After") == "3600"
    finally:
        app.dependency_overrides.clear()
        for e in emails:
            await _delete_user_by_email(db_session, e)


async def test_retry_after_login_usa_lockout(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El 429 de /token (lockout) trae Retry-After == auth_login_lockout_seconds."""
    monkeypatch.setattr(
        "app.core.ratelimit.get_settings",
        lambda: _ratelimit_settings(max_attempts=2),
    )
    monkeypatch.setattr(
        "app.api.v1.auth.get_settings",
        lambda: _ratelimit_settings(max_attempts=2),
    )
    email = "retryafter.login@example.com"
    client = await _client(db_session)
    try:
        async with client:
            reg = await client.post(
                "/v1/auth/register", json={"email": email, "password": "supersecreta1"}
            )
            assert reg.status_code == 201
            # 2 fallos -> lockout; el 3ro da 429.
            for _ in range(2):
                await client.post(
                    "/v1/auth/token", json={"email": email, "password": "mal-password"}
                )
            r429 = await client.post(
                "/v1/auth/token", json={"email": email, "password": "mal-password"}
            )
        assert r429.status_code == 429
        # Retry-After == lockout del login (900), no la ventana del register.
        assert r429.headers.get("Retry-After") == "900"
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


# ---------------------------------------------------------------------------
# 33. /auth/refresh rate-limit por (ip, sub) -> 429 tras el threshold (S4)
# ---------------------------------------------------------------------------


async def test_refresh_rate_limit_429(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N+1 /refresh del mismo (ip, sub) -> 429; shape sin oráculo, con Retry-After.

    El refresh es single-use: cada rotación devuelve un refresh NUEVO con el mismo
    sub. El bucket del rate-limit es por (ip, sub), así que rotar N+1 veces cruza el
    techo aunque cada token sea distinto. Con refresh_max=2: 2 rotaciones OK, la 3ra
    da 429 (NO un 401: el rate-limit corre ANTES de tocar Redis para rotar).
    """
    monkeypatch.setattr(
        "app.core.ratelimit.get_settings",
        lambda: _ratelimit_settings(refresh_max=2),
    )
    monkeypatch.setattr(
        "app.api.v1.auth.get_settings",
        lambda: _ratelimit_settings(refresh_max=2),
    )
    email = "rl.refresh@example.com"
    store = InMemoryTokenStore()
    client = await _client(db_session, store=store)
    try:
        async with client:
            _, _, refresh = await _register_and_login(client, email=email, password="supersecreta1")
            # 2 rotaciones permitidas (threshold 2); cada una devuelve un refresh nuevo.
            for _ in range(2):
                r = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
                assert r.status_code == 200
                refresh = r.json()["refresh_token"]
            # La 3ra cruza el techo por (ip, sub) -> 429.
            r429 = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
        assert r429.status_code == 429
        assert "demasiados" in r429.json()["detail"]
        # Retry-After == ventana del refresh (900).
        assert r429.headers.get("Retry-After") == "900"
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


async def test_refresh_rate_limit_fail_open(db_session: AsyncSession) -> None:
    """Con un store que degrada (Redis caído), /refresh NO se bloquea (fail-open).

    El RedisTokenStore que envuelve un cliente que lanza atrapa y degrada:
    ``incr_with_ttl`` => 0 (no bloquea el rate-limit) y ``revoke_if_absent`` => True
    (rota igual). Un refresh válido sigue dando 200, nunca un 429 espurio.
    """
    from app.core.token_store import RedisTokenStore

    class _BoomRedisClient:
        async def exists(self, *a: object) -> int:
            raise RuntimeError("redis down")

        async def set(self, *a: object, **k: object) -> None:
            raise RuntimeError("redis down")

        async def incr(self, *a: object) -> int:
            raise RuntimeError("redis down")

        async def expire(self, *a: object, **k: object) -> None:
            raise RuntimeError("redis down")

        async def eval(self, *a: object, **k: object) -> int:
            raise RuntimeError("redis down")

        async def mget(self, *a: object) -> list[None]:
            raise RuntimeError("redis down")

        async def delete(self, *a: object) -> None:
            raise RuntimeError("redis down")

    email = "rl.refresh.failopen@example.com"
    # Sembrar + loguear con un store sano; rotar con el boom.
    setup_client = await _client(db_session)
    try:
        async with setup_client:
            _, _, refresh = await _register_and_login(
                setup_client, email=email, password="supersecreta1"
            )
        app.dependency_overrides.clear()

        store = RedisTokenStore(_BoomRedisClient())
        client = await _client(db_session, store=store)
        async with client:
            resp = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
        # fail-open: Redis caído no bloquea ni rompe la rotación.
        assert resp.status_code == 200
        assert resp.json()["access_token"]
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


def _ratelimit_settings(*, max_attempts: int = 5, register_max: int = 10, refresh_max: int = 30):
    """Settings determinista para los tests de rate-limit (thresholds chicos)."""
    from app.core.config import Settings

    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="test-secret-no-usar-en-prod-min-32b",
        AUTH_LOGIN_MAX_ATTEMPTS=max_attempts,
        AUTH_LOGIN_WINDOW_SECONDS=900,
        AUTH_LOGIN_LOCKOUT_SECONDS=900,
        AUTH_REGISTER_MAX_ATTEMPTS=register_max,
        AUTH_REGISTER_WINDOW_SECONDS=3600,
        AUTH_REFRESH_MAX_ATTEMPTS=refresh_max,
        AUTH_REFRESH_WINDOW_SECONDS=900,
    )


# ===========================================================================
# Item 1 de #142 — sid (familia) + reuse-detection retry-safe + aislamiento
# ===========================================================================


def _refresh_sid(refresh_token: str) -> str | None:
    """Decodifica un refresh y devuelve su claim sid (None si no tiene)."""
    return verify_token(refresh_token, expected_type="refresh").get("sid")


def _access_sid(access_token: str) -> str | None:
    """Decodifica un access y devuelve su claim sid (None si no tiene)."""
    return verify_access_token(access_token).get("sid")


def _mint_refresh_with_jti_no_sid(sub: str) -> str:
    """Mintea a mano un refresh CON jti+type pero SIN sid (token pre-item 1)."""
    from datetime import UTC, datetime, timedelta

    import jwt

    from app.core.config import get_settings

    settings = get_settings()
    return jwt.encode(
        {
            "sub": sub,
            "type": "refresh",
            "jti": uuid.uuid4().hex,
            "exp": datetime.now(UTC) + timedelta(days=30),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


async def test_token_emite_sid_en_ambos(db_session: AsyncSession) -> None:
    """/token: el access y el refresh comparten el MISMO sid (misma familia)."""
    email = "sid.both@example.com"
    client = await _client(db_session)
    try:
        async with client:
            _, access, refresh = await _register_and_login(
                client, email=email, password="supersecreta1"
            )
        access_sid = _access_sid(access)
        refresh_sid = _refresh_sid(refresh)
        assert access_sid is not None
        assert refresh_sid is not None
        assert access_sid == refresh_sid
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


async def test_refresh_propaga_sid(db_session: AsyncSession) -> None:
    """/refresh: el nuevo access + refresh comparten el sid del refresh original."""
    email = "sid.propaga@example.com"
    client = await _client(db_session)
    try:
        async with client:
            _, _, refresh = await _register_and_login(client, email=email, password="supersecreta1")
            original_sid = _refresh_sid(refresh)
            resp = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
            assert resp.status_code == 200
            body = resp.json()
        assert original_sid is not None
        # El sid se propaga (la familia sobrevive a la rotación).
        assert _access_sid(body["access_token"]) == original_sid
        assert _refresh_sid(body["refresh_token"]) == original_sid
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


async def test_access_hermano_muere_con_la_familia(db_session: AsyncSession) -> None:
    """La family-revocation mata el access ORIGINAL, no solo el refresh reusado.

    Demuestra que revocar la familia (vía reuse fuera del grace) cierra el agujero
    de "el access robado vive 7 días": el access del login original (no el refresh
    reusado) pasa a 401 en /me.
    """
    email = "sid.hermano@example.com"
    store = InMemoryTokenStore()
    client = await _client(db_session, store=store)
    try:
        async with client:
            _, access, refresh = await _register_and_login(
                client, email=email, password="supersecreta1"
            )
            # Antes del breach el access vale.
            before = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
            assert before.status_code == 200
            # Rotar, luego reusar fuera del grace -> revoca la familia.
            await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
            store.advance(31)
            reuse = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
            assert reuse.status_code == 401
            after = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert after.status_code == 401
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


async def test_sesiones_distinto_sid_no_se_afectan(db_session: AsyncSession) -> None:
    """Aislamiento: revocar la familia A (breach) no afecta el access de la sesión B.

    Dos logins del MISMO user generan dos sid distintos. Un breach en la sesión A
    (reuse fuera del grace) revoca SOLO la familia A; el access de B sigue valiendo.
    """
    email = "sid.aislamiento@example.com"
    password = "supersecreta1"
    store = InMemoryTokenStore()
    client = await _client(db_session, store=store)
    try:
        async with client:
            reg = await client.post(
                "/v1/auth/register", json={"email": email, "password": password}
            )
            assert reg.status_code == 201
            # Sesión A.
            tok_a = await client.post("/v1/auth/token", json={"email": email, "password": password})
            refresh_a = tok_a.json()["refresh_token"]
            # Sesión B (otro login -> otro sid).
            tok_b = await client.post("/v1/auth/token", json={"email": email, "password": password})
            access_b = tok_b.json()["access_token"]
            # Las dos sesiones tienen distinto sid.
            assert _refresh_sid(refresh_a) != _access_sid(access_b)
            # Breach en A: rotar + reusar fuera del grace.
            await client.post("/v1/auth/refresh", json={"refresh_token": refresh_a})
            store.advance(31)
            reuse_a = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_a})
            assert reuse_a.status_code == 401
            # El access de B sigue vivo (otra familia).
            me_b = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {access_b}"})
        assert me_b.status_code == 200
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


async def test_logout_mata_la_familia(db_session: AsyncSession) -> None:
    """Logout revoca la familia: el access Y el refresh de esa sesión mueren.

    Extiende test_logout_blocklistea_access: el logout (sin mandar el refresh en el
    body) igual mata el refresh de la familia porque revoca por sid. El access da
    401 en /me y el refresh da 401 en /refresh.
    """
    email = "sid.logout@example.com"
    store = InMemoryTokenStore()
    client = await _client(db_session, store=store)
    try:
        async with client:
            _, access, refresh = await _register_and_login(
                client, email=email, password="supersecreta1"
            )
            out = await client.post(
                "/v1/auth/logout",
                json={},  # NO mandamos el refresh: la familia lo cubre igual.
                headers={"Authorization": f"Bearer {access}"},
            )
            assert out.status_code == 204
            # El access de la sesión murió.
            me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
            assert me.status_code == 401
            # El refresh de la MISMA familia también murió, aunque no fue al body.
            ref = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
        assert ref.status_code == 401
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


async def test_refresh_compat_token_sin_sid(db_session: AsyncSession) -> None:
    """Compat: un refresh con jti pero SIN sid (pre-item 1) rota OK (arranca familia)."""
    email = "sid.compat.ok@example.com"
    client = await _client(db_session)
    try:
        async with client:
            user_id, _, _ = await _register_and_login(client, email=email, password="supersecreta1")
            legacy_refresh = _mint_refresh_with_jti_no_sid(user_id)
            resp = await client.post("/v1/auth/refresh", json={"refresh_token": legacy_refresh})
            assert resp.status_code == 200
            body = resp.json()
        # Rama 1: arranca una familia nueva (el nuevo par tiene un sid fresco).
        assert _access_sid(body["access_token"]) is not None
        assert _refresh_sid(body["refresh_token"]) is not None
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


async def test_refresh_reuse_token_sin_sid_401_sin_nukear(
    db_session: AsyncSession,
) -> None:
    """Compat: reusar un refresh SIN sid -> 401 (rama 3 sin family-revoke, no crashea).

    Sin sid no hay familia que revocar: el reuse degrada al single-use de #142 (401
    uniforme) sin intentar una family-revocation imposible.
    """
    email = "sid.compat.reuse@example.com"
    store = InMemoryTokenStore()
    client = await _client(db_session, store=store)
    try:
        async with client:
            user_id, _, _ = await _register_and_login(client, email=email, password="supersecreta1")
            legacy_refresh = _mint_refresh_with_jti_no_sid(user_id)
            first = await client.post("/v1/auth/refresh", json={"refresh_token": legacy_refresh})
            assert first.status_code == 200
            # Reusar el viejo sin sid: 401 (sin sid no entra a rama 2 ni nukea nada).
            reuse = await client.post("/v1/auth/refresh", json={"refresh_token": legacy_refresh})
        assert reuse.status_code == 401
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)


async def test_no_leak_sid_en_errores(db_session: AsyncSession) -> None:
    """El sid NO aparece en el response.text de un 401 de /refresh (higiene, regla #4)."""
    email = "sid.noleak@example.com"
    store = InMemoryTokenStore()
    client = await _client(db_session, store=store)
    try:
        async with client:
            _, _, refresh = await _register_and_login(client, email=email, password="supersecreta1")
            sid = _refresh_sid(refresh)
            # Forzar la rama 3 (breach): rotar + reusar fuera del grace.
            await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
            store.advance(31)
            reuse = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
        assert reuse.status_code == 401
        assert sid is not None
        # El sid no se filtra en el cuerpo del 401.
        assert sid not in reuse.text
    finally:
        app.dependency_overrides.clear()
        await _delete_user_by_email(db_session, email)
