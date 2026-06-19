"""Tests de INTEGRACIÓN del endpoint de audit del panel admin (``GET /v1/admin/audit``).

Invariante CLAVE de soberanía (regla #4): la vista admin del ``audit_log`` NUNCA expone
``record_hash`` (cadena de integridad) ni ``target_id`` (estructura interna del moat).
Ambos están ausentes del schema (``AdminAuditRow``) y del SELECT del endpoint. Este test
siembra una fila con un ``record_hash`` y un ``target_id`` reconocibles y verifica que
ninguno aparece en la respuesta.

Setup espejado de ``tests/api/test_sessions.py`` (``httpx.AsyncClient`` +
``ASGITransport(app=app)``, override de ``get_db``, JWT del admin). El GET es read-only.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import create_access_token
from app.enums import AuditOperation, MemoryLayer, Mode
from app.main import app
from app.models.audit import AuditLog
from app.models.user import User

pytestmark = pytest.mark.integration

# record_hash reconocible (64 hex, matchea el CHECK ``^[0-9a-f]{64}$`` de audit_log).
_RECORD_HASH = "a" * 64


async def _seed_admin(session: AsyncSession) -> User:
    """Inserta un User admin y hace flush para que tenga id asignado."""
    user = User(is_admin=True)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_audit(
    session: AsyncSession, *, user_id: uuid.UUID, target_id: uuid.UUID
) -> AuditLog:
    """Inserta una fila de audit con record_hash + target_id reconocibles."""
    row = AuditLog(
        user_id=user_id,
        operation=AuditOperation.WRITE,
        target_layer=MemoryLayer.SEMANTIC,
        target_id=target_id,
        origin_mode=Mode.PRODUCTIVIDAD,
        record_hash=_RECORD_HASH,
        sensitive=False,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession) -> httpx.AsyncClient:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_admin_audit_never_exposes_record_hash_or_target_id(
    db_session: AsyncSession,
) -> None:
    """La respuesta del audit admin NO contiene ``record_hash`` ni ``target_id``."""
    admin = await _seed_admin(db_session)
    target_id = uuid.uuid4()
    row = await _seed_audit(db_session, user_id=admin.id, target_id=target_id)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/admin/audit", headers=_bearer(admin.id))

        assert resp.status_code == 200
        body = resp.json()
        # La fila sembrada aparece (filtra por la ventana default 7d).
        ids = [item["id"] for item in body["items"]]
        assert str(row.id) in ids

        # Invariante de soberanía: ni el record_hash ni el target_id viajan, en NINGÚN lado.
        assert _RECORD_HASH not in resp.text
        assert str(target_id) not in resp.text
        seeded = next(item for item in body["items"] if item["id"] == str(row.id))
        assert "record_hash" not in seeded
        assert "target_id" not in seeded
        # Sí viajan los campos exponibles.
        assert seeded["operation"] == AuditOperation.WRITE.value
        assert seeded["target_layer"] == MemoryLayer.SEMANTIC.value
        assert seeded["sensitive"] is False
        assert "sensitive_pct" in body
    finally:
        app.dependency_overrides.clear()
