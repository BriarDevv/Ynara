"""Tests de INTEGRACIÓN del ``audit_log`` (tabla sagrada — el test solo LEE/inserta
filas, NUNCA modifica el modelo ni la migración; regla #3).

Corren contra el Postgres REAL vía ``db_session`` (savepoint + rollback al final:
no persisten nada entre tests). Requieren ``TEST_DATABASE_URL`` y el marker
``-m integration``.

Invariante cubierto — **ON DELETE CASCADE** (``app/models/audit.py`` línea
``ForeignKey("users.id", ondelete="CASCADE")``; migración inicial
``fk_audit_log_user_id_users`` con ``ondelete="CASCADE"``):

1. ``test_audit_log_row_persists_and_is_readable`` — una fila de ``audit_log``
   sembrada para un user se persiste y se relee con ``select()`` (sanity del FK
   + de las columnas reales de la tabla).
2. ``test_audit_log_cascades_on_user_delete`` — al borrar el ``User`` dueño con un
   ``DELETE`` a nivel DB (Core, no ``session.delete`` — así se ejercita el FK de
   Postgres, no la cascada ORM de la relación), la fila de ``audit_log`` del user
   desaparece por ``ON DELETE CASCADE``.
3. ``test_audit_log_cascade_isolated_per_user`` — borrar el user A no toca la fila
   de audit del user B (la cascada está acotada por el FK ``user_id``).

NOTA (regla #4): el ``audit_log`` NO guarda texto de usuario (solo metadata de la
operación + ``record_hash``); ningún test loguea ni asierta contenido de memoria.

NOTA DE SCOPE — la escritura real de ``audit_log`` ya existe (issue #158):
``app/llm/memory_engine.apply_ops`` inserta una fila por op de memoria consolidada
vía ``app/memory/audit.AuditStore``; esa cobertura vive en
``tests/integration/test_audit_writes.py``. Estos tests se mantienen enfocados en
el invariante de FK que NO depende de quién escribió la fila: siembran la fila de
``audit_log`` directamente vía ORM (escribir en ``audit_log`` está permitido; lo
prohibido es tocar el modelo o la migración) y cubren el ``ON DELETE CASCADE``.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.models.audit import AuditLog
from app.models.user import User

# ---------------------------------------------------------------------------
# Helpers de siembra
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession) -> User:
    """Inserta un User mínimo y lo retorna (flush, no commit — rollback al final)."""
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_audit_row(session: AsyncSession, user: User) -> AuditLog:
    """Inserta una fila de ``audit_log`` para ``user`` y la retorna (flush, no commit).

    Replica una op de escritura de memoria semántica (``operation=WRITE``,
    ``target_layer=SEMANTIC``). El ``record_hash`` es un sha256 hex válido (CHECK
    ``record_hash_sha256_hex``); NO contiene texto de usuario (regla #4). El test
    solo INSERTA en ``audit_log`` — no modifica el modelo ni la migración (regla #3).
    """
    row = AuditLog(
        user_id=user.id,
        operation=AuditOperation.WRITE,
        target_layer=MemoryLayer.SEMANTIC,
        target_id=uuid.uuid4(),
        origin_model=LlmModel.QWEN,
        origin_mode=Mode.PRODUCTIVIDAD,
        origin_tool="memory.add",
        record_hash="a" * 64,  # sha256 hex válido, sin contenido de usuario
        sensitive=False,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def _audit_exists(session: AsyncSession, audit_id: uuid.UUID) -> bool:
    """``True`` si la fila de ``audit_log`` con ese id existe en la DB."""
    stmt = select(AuditLog.id).where(AuditLog.id == audit_id)
    return (await session.execute(stmt)).scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# 1. Sanity — la fila de audit se persiste y se relee
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_audit_log_row_persists_and_is_readable(db_session: AsyncSession) -> None:
    """Una fila de ``audit_log`` sembrada para un user se persiste y se relee.

    Sanity del FK ``user_id`` y de las columnas reales de la tabla: un ``select()``
    crudo devuelve la fila con la metadata sembrada (sin tocar texto de usuario).
    """
    user = await _seed_user(db_session)
    audit = await _seed_audit_row(db_session, user)

    stmt = select(AuditLog).where(AuditLog.id == audit.id)
    row = (await db_session.execute(stmt)).scalar_one()

    assert row.user_id == user.id
    assert row.operation == AuditOperation.WRITE
    assert row.target_layer == MemoryLayer.SEMANTIC
    assert row.record_hash == "a" * 64
    assert row.sensitive is False
    assert row.created_at is not None, "created_at lo pone el server_default"


# ---------------------------------------------------------------------------
# 2. ON DELETE CASCADE — borrar el user borra su audit_log
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_audit_log_cascades_on_user_delete(db_session: AsyncSession) -> None:
    """Al borrar el ``User`` dueño, su fila de ``audit_log`` desaparece (CASCADE).

    Se usa un ``DELETE`` a nivel DB (Core ``sa_delete`` por ``id``), NO
    ``session.delete(user)``: así el borrado lo ejecuta Postgres y se ejercita el
    FK ``fk_audit_log_user_id_users`` con ``ondelete="CASCADE"`` (la cascada REAL
    de la migración), no la cascada ``delete-orphan`` de la relación ORM.
    """
    user = await _seed_user(db_session)
    audit = await _seed_audit_row(db_session, user)

    # Pre-condición: la fila de audit existe.
    assert await _audit_exists(db_session, audit.id) is True

    # DELETE a nivel DB del user → Postgres aplica el ON DELETE CASCADE del FK.
    await db_session.execute(sa_delete(User).where(User.id == user.id))
    await db_session.flush()

    # El user ya no está...
    user_remaining = (
        await db_session.execute(select(User.id).where(User.id == user.id))
    ).scalar_one_or_none()
    assert user_remaining is None, "el user debe haberse borrado"

    # ...y su fila de audit se borró por CASCADE (query crudo confirma 0 filas).
    assert await _audit_exists(db_session, audit.id) is False, (
        "audit_log debe borrarse por ON DELETE CASCADE al borrar el user"
    )


# ---------------------------------------------------------------------------
# 3. CASCADE acotada por user — borrar A no toca el audit de B
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_audit_log_cascade_isolated_per_user(db_session: AsyncSession) -> None:
    """Borrar el user A cascada SOLO su audit; la fila de B queda intacta.

    El ``ON DELETE CASCADE`` está acotado por el FK ``user_id``: el DELETE de A no
    arrastra filas de audit de otros usuarios.
    """
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    audit_a = await _seed_audit_row(db_session, user_a)
    audit_b = await _seed_audit_row(db_session, user_b)

    # Borrar SOLO el user A.
    await db_session.execute(sa_delete(User).where(User.id == user_a.id))
    await db_session.flush()

    # El audit de A se fue por CASCADE; el de B sigue presente.
    assert await _audit_exists(db_session, audit_a.id) is False, (
        "el audit de A debe borrarse al borrar A"
    )
    assert await _audit_exists(db_session, audit_b.id) is True, (
        "el audit de B no debe verse afectado por el DELETE de A"
    )
