"""Tests de INTEGRACIÓN del worker de retention de ``episodic_memory`` (tabla sagrada).

El test solo INSERTA/borra filas vía el worker; NUNCA modifica el modelo ni la
migración (regla #3). Corren contra el Postgres REAL vía ``db_session`` (savepoint
+ rollback al final). Requieren ``TEST_DATABASE_URL`` y el marker ``-m integration``.

Cubre que ``_async_purge_episodic`` borra los episodios cuya ventana
(``created_at + retention_days``) ya venció y respeta los recientes y el borde
EXACTO; y que el conteo viene diferenciado por ``is_sensitive`` (roadmap §5.3). El
``now`` se inyecta para que el cutoff per-row sea determinista (igual que
``audit_retention.py`` / ``decay.py``).

NOTA (regla #4): el ``summary`` se siembra como ``BYTEA`` opaco; el worker NUNCA lo
descifra (borra por tiempo). Ningún test asierta contenido de memoria.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import Mode
from app.models.memory import EpisodicMemory
from app.models.session import ChatSession
from app.models.user import User
from app.workflows.episodic_retention import _async_purge_episodic

# Vector opaco para summary_embedding (no se busca; solo se persiste/borra).
_ZERO_VEC = [0.0] * 1024


# ---------------------------------------------------------------------------
# Helpers de siembra
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_session(session: AsyncSession, *, user_id: uuid.UUID) -> ChatSession:
    """Una ChatSession por episodio (session_id es UNIQUE en episodic_memory)."""
    cs = ChatSession(user_id=user_id, mode=Mode.VIDA)
    session.add(cs)
    await session.flush()
    await session.refresh(cs)
    return cs


async def _seed_episodic(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    created_at: datetime,
    retention_days: int,
    is_sensitive: bool,
) -> EpisodicMemory:
    """Inserta un episodio con ``created_at`` + ``retention_days`` explícitos.

    El ``created_at`` se setea a mano (override del ``server_default=func.now()``)
    para ubicar el episodio a un lado u otro de su ventana de retention. El
    ``summary`` es ``BYTEA`` opaco (el worker no lo descifra). Crea su propia
    ChatSession (FK NOT NULL UNIQUE).
    """
    cs = await _seed_session(session, user_id=user_id)
    row = EpisodicMemory(
        user_id=user_id,
        session_id=cs.id,
        summary=b"\x00" * 16,
        summary_embedding=_ZERO_VEC,
        is_sensitive=is_sensitive,
        retention_days=retention_days,
        occurred_at=created_at,
        topics={},
        created_at=created_at,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def _episodic_exists(session: AsyncSession, episodic_id: uuid.UUID) -> bool:
    stmt = select(EpisodicMemory.id).where(EpisodicMemory.id == episodic_id)
    return (await session.execute(stmt)).scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# 1. Borra lo vencido (sensible + no-sensible), respeta lo reciente; conteo diferenciado
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_purge_deletes_expired_keeps_recent(db_session: AsyncSession) -> None:
    """Borra los episodios vencidos y conserva los dentro de ventana; cuenta diferenciado."""
    now = datetime.now(UTC)
    user = await _seed_user(db_session)

    # Vencido no-sensible: 365d de retention, creado hace 365+30 días -> expira.
    expired_default = await _seed_episodic(
        db_session,
        user_id=user.id,
        created_at=now - timedelta(days=365 + 30),
        retention_days=365,
        is_sensitive=False,
    )
    # Vencido SENSIBLE: 180d de retention (Bienestar), creado hace 180+10 días -> expira.
    expired_sensitive = await _seed_episodic(
        db_session,
        user_id=user.id,
        created_at=now - timedelta(days=180 + 10),
        retention_days=180,
        is_sensitive=True,
    )
    # Reciente: 365d de retention, creado hace 10 días -> NO expira.
    recent = await _seed_episodic(
        db_session,
        user_id=user.id,
        created_at=now - timedelta(days=10),
        retention_days=365,
        is_sensitive=False,
    )

    sensitive_deleted, non_sensitive_deleted = await _async_purge_episodic(
        session=db_session, now=now
    )

    assert sensitive_deleted == 1, "el episodio sensible vencido se borra"
    assert non_sensitive_deleted == 1, "el episodio no-sensible vencido se borra"
    assert await _episodic_exists(db_session, expired_default.id) is False
    assert await _episodic_exists(db_session, expired_sensitive.id) is False
    assert await _episodic_exists(db_session, recent.id) is True, "el reciente queda"


# ---------------------------------------------------------------------------
# 2. El borde EXACTO de la ventana queda (predicado < estricto)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_purge_keeps_boundary_exact(db_session: AsyncSession) -> None:
    """Un episodio creado exacto en el borde (created_at + retention_days == now) queda.

    El predicado es ``created_at + retention_days < now`` (estricto): es la guarda
    contra una regresión ``<`` -> ``<=``.
    """
    now = datetime.now(UTC)
    user = await _seed_user(db_session)

    # La invariante del borde depende de aritmética de DÍAS (no meses/años): el
    # predicado usa ``retention_days * interval '1 day'``, exacto ``365*86400s``, que
    # cancela contra el ``timedelta(days=365)`` de Python sin drift de calendario.
    # created_at + 365d == now exacto -> NO < now -> queda.
    at_cutoff = await _seed_episodic(
        db_session,
        user_id=user.id,
        created_at=now - timedelta(days=365),
        retention_days=365,
        is_sensitive=False,
    )
    # 1 día dentro de la ventana -> queda.
    just_inside = await _seed_episodic(
        db_session,
        user_id=user.id,
        created_at=now - timedelta(days=364),
        retention_days=365,
        is_sensitive=False,
    )

    sensitive_deleted, non_sensitive_deleted = await _async_purge_episodic(
        session=db_session, now=now
    )

    assert (sensitive_deleted, non_sensitive_deleted) == (0, 0), "nada en ventana se borra"
    assert await _episodic_exists(db_session, at_cutoff.id) is True
    assert await _episodic_exists(db_session, just_inside.id) is True
