"""Round-trip de enums contra Postgres real (integration, issue #23).

Complementa ``test_enum_pg_values.py`` (lado ORM, sin DB): inserta filas con
cada valor de enum y confirma que el tipo PG materializado por la migracion
(``values_callable=enum_values``, en minuscula) los acepta en un INSERT real
y los devuelve igual en el SELECT.

Marcado ``integration``: usa la fixture ``db_session`` (``conftest.py``), que
SKIPea si no hay ``TEST_DATABASE_URL`` (DB dedicada con el schema aplicado,
``alembic upgrade head``). Nunca corre contra prod.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.models.audit import AuditLog
from app.models.session import ChatSession
from app.models.user import User

pytestmark = pytest.mark.integration


async def test_session_mode_roundtrip(db_session: AsyncSession) -> None:
    """Cada Mode se inserta y vuelve igual: valida el tipo PG mode_enum."""
    user = User()
    db_session.add(user)
    await db_session.flush()

    for mode in Mode:
        db_session.add(ChatSession(user_id=user.id, mode=mode))
    await db_session.flush()
    db_session.expire_all()  # fuerza un SELECT real, no el identity-map

    stored = set((await db_session.execute(select(ChatSession.mode))).scalars().all())
    assert stored == set(Mode)


async def test_audit_enums_roundtrip(db_session: AsyncSession) -> None:
    """Los 4 enums del audit_log round-trippean contra sus tipos PG nativos."""
    user = User()
    db_session.add(user)
    await db_session.flush()

    entry = AuditLog(
        user_id=user.id,
        operation=AuditOperation.WRITE,
        target_layer=MemoryLayer.SEMANTIC,
        origin_model=LlmModel.QWEN,
        origin_mode=Mode.PRODUCTIVIDAD,
        record_hash="a" * 64,  # valido para el CHECK ^[0-9a-f]{64}$
    )
    db_session.add(entry)
    await db_session.flush()
    db_session.expire_all()

    row = (await db_session.execute(select(AuditLog).where(AuditLog.id == entry.id))).scalar_one()
    assert row.operation is AuditOperation.WRITE
    assert row.target_layer is MemoryLayer.SEMANTIC
    assert row.origin_model is LlmModel.QWEN
    assert row.origin_mode is Mode.PRODUCTIVIDAD
