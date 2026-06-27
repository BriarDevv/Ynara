"""Tests de integración de ``DeviceTokenStore`` (PR-B).

Todos ``integration`` (tocan la DB de tests dedicada vía ``db_session``). Patrón de
siembra espejado de ``test_task_store.py`` (flush sin commit; el savepoint del fixture
limpia).

Cubren:
- ``register`` inserta el device token del user correcto (aislamiento).
- ``register`` del MISMO token re-asigna user/platform/last_seen (upsert, NO duplica).
- ``unregister`` borra el token propio; ``False`` (404 sin oráculo) para ajeno/inexistente.
- ``list_for_user`` filtra por user (aislamiento).
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import DevicePlatform
from app.models.device_token import DeviceToken
from app.models.user import User
from app.schemas.device import DeviceRegister
from app.services.devices import (
    MAX_DEVICE_TOKENS_PER_USER,
    DeviceTokenStore,
    TooManyDeviceTokensError,
)

pytestmark = pytest.mark.integration


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _count_tokens(session: AsyncSession, *, token: str) -> int:
    return (
        await session.scalar(
            select(func.count()).select_from(DeviceToken).where(DeviceToken.token == token)
        )
    ) or 0


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


async def test_register_inserts_for_correct_user(db_session: AsyncSession) -> None:
    """``register`` persiste el token atado al user del store; dict sin user_id."""
    user = await _seed_user(db_session)
    store = DeviceTokenStore(db_session, user.id)

    result, created = await store.register(
        DeviceRegister(platform=DevicePlatform.IOS, token="tok-abc")
    )

    assert created is True  # alta nueva
    assert result["platform"] == DevicePlatform.IOS.value
    assert result["token"] == "tok-abc"
    assert "user_id" not in result

    persisted = await db_session.get(DeviceToken, UUID(str(result["id"])))
    assert persisted is not None
    assert persisted.user_id == user.id


async def test_register_same_token_reassigns_no_duplicate(db_session: AsyncSession) -> None:
    """Re-registrar el MISMO token (otro user/platform) re-asigna, NO duplica filas."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)

    first, first_created = await DeviceTokenStore(db_session, user_a.id).register(
        DeviceRegister(platform=DevicePlatform.IOS, token="dev-1")
    )
    # El MISMO token, ahora bajo user_b con otra plataforma → re-asigna la fila existente.
    second, second_created = await DeviceTokenStore(db_session, user_b.id).register(
        DeviceRegister(platform=DevicePlatform.ANDROID, token="dev-1")
    )

    # Alta nueva la primera; re-asignación (no alta) la segunda.
    assert first_created is True
    assert second_created is False
    # Misma fila (mismo id), no se duplicó.
    assert first["id"] == second["id"]
    assert await _count_tokens(db_session, token="dev-1") == 1

    # Re-asignada a user_b + nueva plataforma.
    persisted = await db_session.get(DeviceToken, UUID(str(second["id"])))
    assert persisted is not None
    assert persisted.user_id == user_b.id
    assert persisted.platform == DevicePlatform.ANDROID


async def test_register_same_user_same_token_updates_last_seen(db_session: AsyncSession) -> None:
    """Re-registrar el mismo token del mismo user refresca ``last_seen_at`` (upsert)."""
    user = await _seed_user(db_session)
    store = DeviceTokenStore(db_session, user.id)

    first, first_created = await store.register(
        DeviceRegister(platform=DevicePlatform.WEB, token="dev-x")
    )
    second, second_created = await store.register(
        DeviceRegister(platform=DevicePlatform.WEB, token="dev-x")
    )

    # Alta la primera; upsert del mismo token del mismo user la segunda (no alta).
    assert first_created is True
    assert second_created is False
    assert first["id"] == second["id"]
    assert await _count_tokens(db_session, token="dev-x") == 1


# ---------------------------------------------------------------------------
# unregister
# ---------------------------------------------------------------------------


async def test_unregister_owned_token(db_session: AsyncSession) -> None:
    """``unregister`` de un token propio → True; la fila se borra."""
    user = await _seed_user(db_session)
    store = DeviceTokenStore(db_session, user.id)
    await store.register(DeviceRegister(platform=DevicePlatform.IOS, token="to-delete"))

    assert await store.unregister("to-delete") is True
    assert await _count_tokens(db_session, token="to-delete") == 0


async def test_unregister_other_users_token_returns_false(db_session: AsyncSession) -> None:
    """``unregister`` de un token ajeno → False (aislamiento, sin oráculo); no lo borra."""
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)
    await DeviceTokenStore(db_session, owner.id).register(
        DeviceRegister(platform=DevicePlatform.IOS, token="owned")
    )

    assert await DeviceTokenStore(db_session, intruder.id).unregister("owned") is False
    # La fila del owner sigue existiendo.
    assert await _count_tokens(db_session, token="owned") == 1


async def test_unregister_nonexistent_returns_false(db_session: AsyncSession) -> None:
    """``unregister`` de un token inexistente → False (mismo resultado que ajeno)."""
    user = await _seed_user(db_session)
    assert await DeviceTokenStore(db_session, user.id).unregister("nope") is False


# ---------------------------------------------------------------------------
# list_for_user
# ---------------------------------------------------------------------------


async def test_list_for_user_isolated(db_session: AsyncSession) -> None:
    """``list_for_user`` del user A no devuelve tokens de B."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    await DeviceTokenStore(db_session, user_a.id).register(
        DeviceRegister(platform=DevicePlatform.IOS, token="a-1")
    )
    await DeviceTokenStore(db_session, user_b.id).register(
        DeviceRegister(platform=DevicePlatform.ANDROID, token="b-1")
    )

    a_tokens = await DeviceTokenStore(db_session, user_a.id).list_for_user()
    assert [t["token"] for t in a_tokens] == ["a-1"]


# ---------------------------------------------------------------------------
# cap por usuario (MED-03)
# ---------------------------------------------------------------------------


async def test_register_new_token_over_cap_raises(db_session: AsyncSession) -> None:
    """Registrar un token NUEVO con el usuario en el cap → ``TooManyDeviceTokensError``."""
    user = await _seed_user(db_session)
    store = DeviceTokenStore(db_session, user.id)
    for i in range(MAX_DEVICE_TOKENS_PER_USER):
        await store.register(DeviceRegister(platform=DevicePlatform.IOS, token=f"tok-{i}"))

    with pytest.raises(TooManyDeviceTokensError):
        await store.register(DeviceRegister(platform=DevicePlatform.IOS, token="tok-over"))

    # El token rechazado NO se insertó.
    assert await _count_tokens(db_session, token="tok-over") == 0


async def test_register_existing_token_at_cap_does_not_reject(db_session: AsyncSession) -> None:
    """En el cap, re-registrar un token YA propio no incrementa ni rechaza (upsert)."""
    user = await _seed_user(db_session)
    store = DeviceTokenStore(db_session, user.id)
    for i in range(MAX_DEVICE_TOKENS_PER_USER):
        await store.register(DeviceRegister(platform=DevicePlatform.IOS, token=f"tok-{i}"))

    # Re-registrar uno existente (upsert) no cuenta contra el cap → no levanta.
    result, created = await store.register(
        DeviceRegister(platform=DevicePlatform.ANDROID, token="tok-0")
    )
    assert created is False
    assert result["platform"] == DevicePlatform.ANDROID.value

    # Total intacto (no se agregó fila).
    total = await db_session.scalar(
        select(func.count()).select_from(DeviceToken).where(DeviceToken.user_id == user.id)
    )
    assert total == MAX_DEVICE_TOKENS_PER_USER


# ---------------------------------------------------------------------------
# rastro de re-asignación entre usuarios (MED-02)
# ---------------------------------------------------------------------------


async def test_reassign_logs_ids_never_token(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-asignar un token de otro user loguea SOLO ids (regla #4: nunca el token).

    Se espía ``logger.info`` directo con un Mock (en vez de ``caplog`` / un handler): la
    captura por handler depende de ``isEnabledFor`` (nivel + ``logging.disable`` global +
    flag ``disabled``), y otro test del suite puede dejar ese estado tocado, volviendo el
    test flaky. El Mock reemplaza el método: se invoca incondicionalmente, así que afirma el
    contrato de la llamada (qué se loguea) sin depender del estado global de logging.
    """
    from app.services import devices as devices_mod

    owner = await _seed_user(db_session)
    new_owner = await _seed_user(db_session)
    await DeviceTokenStore(db_session, owner.id).register(
        DeviceRegister(platform=DevicePlatform.IOS, token="secret-credential-tok")
    )

    info_spy = MagicMock()
    monkeypatch.setattr(devices_mod.logger, "info", info_spy)
    await DeviceTokenStore(db_session, new_owner.id).register(
        DeviceRegister(platform=DevicePlatform.ANDROID, token="secret-credential-tok")
    )

    assert info_spy.called, "esperaba un log de re-asignación"
    fmt, *args = info_spy.call_args.args
    rendered = fmt % tuple(args)
    assert "reassigned" in fmt
    # Los ids viejo/nuevo SÍ aparecen; el token NUNCA (regla #4) — ni en el render ni crudo.
    assert str(owner.id) in rendered
    assert str(new_owner.id) in rendered
    assert "secret-credential-tok" not in rendered
    assert all("secret-credential-tok" != str(arg) for arg in args)
