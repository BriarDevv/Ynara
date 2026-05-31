"""Tests del worker de decay de memoria procedural (M8 Ola 3, ADR-007 D1).

UNIT: validan el wrapper Celery ``decay_procedural`` y la cadencia del beat sin
  DB ni red.
INTEGRATION: validan ``_async_decay`` contra la DB de tests real
  (``@pytest.mark.integration``), sembrando entradas procedural con
  ``last_reinforced_at`` / ``confidence`` controlados via INSERT ORM directo
  (bypass del store ``upsert``, que resetearia el decay).

Reglas aplicadas:
- Tabla SAGRADA: UPDATE/DELETE SQL directo, NUNCA upsert (regla #3).
- Ningun dato de usuario en logs (regla #4): el wrapper solo loguea conteos.
- UTC-aware datetimes en toda la siembra.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import ProceduralMemory
from app.models.user import User
from app.workflows.decay import (
    DECAY_FACTOR,
    DECAY_INTERVAL_DAYS,
    HARD_DELETE_MIN_DAYS,
    DecayResult,
    _async_decay,
    decay_procedural,
)

# ---------------------------------------------------------------------------
# Helpers de siembra (solo para tests de integracion)
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession) -> UUID:
    """Inserta un User minimo y devuelve su UUID. Flush sin commit."""
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user.id


async def _seed_procedural(
    session: AsyncSession,
    *,
    user_id: UUID,
    key: str,
    confidence: float,
    last_reinforced_at: datetime,
    value: dict | None = None,
    stale: bool = False,
) -> ProceduralMemory:
    """Inserta una entrada procedural por ORM directo (bypass del store).

    El store ``upsert`` resetea ``confidence=1.0`` / ``last_reinforced_at=now()``
    / ``stale=false`` al reforzar; aca necesitamos controlar esos valores para
    probar el decay, asi que insertamos el modelo directo.
    """
    entry = ProceduralMemory(
        user_id=user_id,
        key=key,
        value=value if value is not None else {"v": key},
        confidence=confidence,
        last_reinforced_at=last_reinforced_at,
        stale=stale,
    )
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def _get(session: AsyncSession, entry_id: UUID) -> ProceduralMemory | None:
    """Relee una entrada por id desde la DB (expira el identity map primero)."""
    session.expire_all()
    stmt = select(ProceduralMemory).where(ProceduralMemory.id == entry_id)
    return (await session.execute(stmt)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# UNIT tests — wrapper + beat, sin DB ni red
# ---------------------------------------------------------------------------


class TestDecayProceduralWrapper:
    """Tests del wrapper Celery ``decay_procedural``."""

    def test_task_name_is_correct(self) -> None:
        """La task esta registrada con el nombre correcto."""
        assert decay_procedural.name == "workflows.decay_procedural"

    def test_calls_async_decay(self) -> None:
        """El wrapper invoca ``_async_decay`` exactamente una vez."""
        with patch(
            "app.workflows.decay._async_decay", new_callable=AsyncMock
        ) as mock_async:
            mock_async.return_value = DecayResult(decayed=3, staled=1, deleted=0)
            result = decay_procedural()

        assert result is None
        mock_async.assert_called_once_with()

    def test_does_not_propagate_if_async_decay_raises(self) -> None:
        """Si ``_async_decay`` lanza, el wrapper NO propaga (worker no muere)."""
        with patch(
            "app.workflows.decay._async_decay", new_callable=AsyncMock
        ) as mock_async:
            mock_async.side_effect = RuntimeError("DB caida")
            # No debe lanzar.
            decay_procedural()

    def test_does_not_propagate_if_asyncio_run_raises(self) -> None:
        """Cualquier excepcion dentro del try queda silenciada."""
        with patch("app.workflows.decay.asyncio.run") as mock_run:
            mock_run.side_effect = ValueError("loop error")
            # No debe lanzar.
            decay_procedural()


class TestBeatSchedule:
    """La cadencia del beat es por-intervalo (cada DECAY_INTERVAL_DAYS dias)."""

    def test_beat_schedule_registers_decay_task(self) -> None:
        """El beat_schedule registra la task de decay con cadencia por-intervalo."""
        from app.workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        entry = schedule["decay-procedural-every-interval"]
        assert entry["task"] == "workflows.decay_procedural"
        assert entry["schedule"] == timedelta(days=DECAY_INTERVAL_DAYS)


# ---------------------------------------------------------------------------
# INTEGRATION tests — contra DB de tests real
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAsyncDecayIntegration:
    """Tests de integracion de ``_async_decay`` contra la DB de tests.

    Usa ``db_session`` (function-scoped, rollback al final). Siembra entradas
    con ``last_reinforced_at`` / ``confidence`` controlados via ORM directo.
    """

    async def test_recent_entry_does_not_decay(self, db_session: AsyncSession) -> None:
        """Una entrada reforzada dentro del intervalo NO decae."""
        user_id = await _seed_user(db_session)
        recent = datetime.now(UTC) - timedelta(days=1)
        entry = await _seed_procedural(
            db_session, user_id=user_id, key="reciente", confidence=0.8,
            last_reinforced_at=recent,
        )

        result = await _async_decay(session=db_session)

        refreshed = await _get(db_session, entry.id)
        assert refreshed is not None
        assert refreshed.confidence == pytest.approx(0.8)
        assert refreshed.stale is False
        assert result.decayed == 0

    async def test_old_entry_decays_by_factor(self, db_session: AsyncSession) -> None:
        """Una entrada no reforzada en el ultimo intervalo decae a confidence*0.9."""
        user_id = await _seed_user(db_session)
        old = datetime.now(UTC) - timedelta(days=DECAY_INTERVAL_DAYS + 1)
        entry = await _seed_procedural(
            db_session, user_id=user_id, key="vieja", confidence=0.8,
            last_reinforced_at=old,
        )

        result = await _async_decay(session=db_session)

        refreshed = await _get(db_session, entry.id)
        assert refreshed is not None
        assert refreshed.confidence == pytest.approx(0.8 * DECAY_FACTOR)
        assert result.decayed >= 1

    async def test_entry_falling_below_threshold_becomes_stale(
        self, db_session: AsyncSession
    ) -> None:
        """Una entrada que cae bajo 0.3 tras decaer queda stale=True."""
        user_id = await _seed_user(db_session)
        old = datetime.now(UTC) - timedelta(days=DECAY_INTERVAL_DAYS + 1)
        # 0.33 * 0.9 = 0.297 < 0.3 -> stale tras el decay.
        entry = await _seed_procedural(
            db_session, user_id=user_id, key="cae_a_stale", confidence=0.33,
            last_reinforced_at=old,
        )

        result = await _async_decay(session=db_session)

        refreshed = await _get(db_session, entry.id)
        assert refreshed is not None
        assert refreshed.confidence == pytest.approx(0.33 * DECAY_FACTOR)
        assert refreshed.confidence < 0.3
        assert refreshed.stale is True
        assert result.staled >= 1

    async def test_above_threshold_not_staled(self, db_session: AsyncSession) -> None:
        """Una entrada que decae pero queda >= 0.3 NO se marca stale."""
        user_id = await _seed_user(db_session)
        old = datetime.now(UTC) - timedelta(days=DECAY_INTERVAL_DAYS + 1)
        # 0.5 * 0.9 = 0.45 >= 0.3 -> no stale.
        entry = await _seed_procedural(
            db_session, user_id=user_id, key="se_mantiene", confidence=0.5,
            last_reinforced_at=old,
        )

        await _async_decay(session=db_session)

        refreshed = await _get(db_session, entry.id)
        assert refreshed is not None
        assert refreshed.confidence == pytest.approx(0.45)
        assert refreshed.stale is False

    async def test_low_confidence_and_old_is_hard_deleted(
        self, db_session: AsyncSession
    ) -> None:
        """confidence < 0.1 Y last_reinforced_at > 90d -> borrado fisico."""
        user_id = await _seed_user(db_session)
        very_old = datetime.now(UTC) - timedelta(days=HARD_DELETE_MIN_DAYS + 1)
        # 0.05 ya esta bajo 0.1; tras decaer (0.045) sigue bajo. last_reinforced
        # muy viejo -> cumple el doble criterio.
        entry = await _seed_procedural(
            db_session, user_id=user_id, key="borrame", confidence=0.05,
            last_reinforced_at=very_old,
        )

        result = await _async_decay(session=db_session)

        refreshed = await _get(db_session, entry.id)
        assert refreshed is None
        assert result.deleted >= 1

    async def test_low_confidence_but_recently_reinforced_not_deleted(
        self, db_session: AsyncSession
    ) -> None:
        """confidence < 0.1 pero reforzada hace poco -> NO se borra (doble criterio).

        La entrada esta reforzada dentro del intervalo, asi que NO decae y NO
        cumple ``last_reinforced_at > 90d``: el doble criterio la protege.
        """
        user_id = await _seed_user(db_session)
        recent = datetime.now(UTC) - timedelta(days=1)
        entry = await _seed_procedural(
            db_session, user_id=user_id, key="baja_pero_fresca", confidence=0.05,
            last_reinforced_at=recent,
        )

        result = await _async_decay(session=db_session)

        refreshed = await _get(db_session, entry.id)
        assert refreshed is not None
        # No decae (reforzada dentro del intervalo) y no se borra.
        assert refreshed.confidence == pytest.approx(0.05)
        assert result.deleted == 0
        # Aun asi queda stale (confidence < 0.3 ya de entrada).
        assert refreshed.stale is True

    async def test_decay_does_not_touch_value_nor_reset_confidence(
        self, db_session: AsyncSession
    ) -> None:
        """El decay NO toca ``value`` ni resetea ``confidence`` (no usa upsert)."""
        user_id = await _seed_user(db_session)
        old = datetime.now(UTC) - timedelta(days=DECAY_INTERVAL_DAYS + 1)
        original_value = {"tipo": "vegetariana", "n": 3}
        original_lra = old
        entry = await _seed_procedural(
            db_session, user_id=user_id, key="con_value", confidence=0.7,
            last_reinforced_at=original_lra, value=original_value,
        )

        await _async_decay(session=db_session)

        refreshed = await _get(db_session, entry.id)
        assert refreshed is not None
        # value intacto.
        assert refreshed.value == original_value
        # confidence DECAYO (no se reseteo a 1.0 como haria el upsert).
        assert refreshed.confidence == pytest.approx(0.7 * DECAY_FACTOR)
        assert refreshed.confidence != 1.0
        # last_reinforced_at intacto (el decay no lo toca; el upsert lo pondria
        # en now()).
        assert refreshed.last_reinforced_at.replace(tzinfo=UTC) == original_lra.replace(
            tzinfo=UTC
        )

    async def test_full_pipeline_counts(self, db_session: AsyncSession) -> None:
        """Una corrida mixta reporta conteos coherentes de los tres pasos."""
        user_id = await _seed_user(db_session)
        recent = datetime.now(UTC) - timedelta(days=1)
        old = datetime.now(UTC) - timedelta(days=DECAY_INTERVAL_DAYS + 1)
        very_old = datetime.now(UTC) - timedelta(days=HARD_DELETE_MIN_DAYS + 1)

        # No decae.
        await _seed_procedural(
            db_session, user_id=user_id, key="fresca", confidence=0.9,
            last_reinforced_at=recent,
        )
        # Decae y cae a stale (0.32*0.9=0.288).
        await _seed_procedural(
            db_session, user_id=user_id, key="a_stale", confidence=0.32,
            last_reinforced_at=old,
        )
        # Decae, baja confianza + muy vieja -> hard delete (0.05*0.9=0.045).
        await _seed_procedural(
            db_session, user_id=user_id, key="a_borrar", confidence=0.05,
            last_reinforced_at=very_old,
        )

        result = await _async_decay(session=db_session)

        # Las dos viejas decaen; la fresca no.
        assert result.decayed == 2
        # Solo "a_stale" transiciona a stale (la borrada se elimina; ya estaba
        # bajo umbral pero el orden marca stale antes del delete).
        assert result.staled >= 1
        assert result.deleted == 1
