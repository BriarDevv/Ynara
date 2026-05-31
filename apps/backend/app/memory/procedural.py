"""Memoria procedural: preferencias y patrones del usuario.

Storage propio sobre la tabla sagrada ``procedural_memory`` (engine in-house,
ADR-010). JSONB estructurado en ``value``, **sin** cifrado y **sin** embeddings
(no es contenido íntimo de texto libre: es preferencia estructurada). Lookup
directo por ``(user_id, key)``.

``ProceduralMemoryStore`` se construye **por request** ligando ``user_id`` en el
``__init__``: el ``user_id`` nunca viaja en los argumentos de los métodos, así
todo query queda forzosamente filtrado por el usuario del store (aislamiento por
construcción, ADR-010 / regla #3). El upsert resetea el decay (``confidence=1.0``,
``last_reinforced_at=now()``, ``stale=false``) al reforzar, según ADR-007 D1.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import ProceduralMemory
from app.schemas.memory import ProceduralMemoryOut, ProceduralMemoryUpsert


class ProceduralMemoryStore:
    """Store por-request de la capa procedural, ligado a un ``user_id``.

    Todo método filtra por ``self._user_id``: el aislamiento entre usuarios es
    estructural (el ``user_id`` no es un argumento que el caller pueda variar).
    """

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    async def upsert(self, payload: ProceduralMemoryUpsert) -> ProceduralMemoryOut:
        """Inserta o refuerza una entrada por ``(user_id, key)``.

        ON CONFLICT ``(user_id, key)`` DO UPDATE: reemplaza ``value`` y **resetea
        el decay** (``confidence=1.0``, ``last_reinforced_at=now()``,
        ``stale=false``) — reforzar una preferencia la revive (ADR-007 D1).
        """
        stmt = (
            pg_insert(ProceduralMemory)
            .values(
                user_id=self._user_id,
                key=payload.key,
                value=payload.value,
            )
            .on_conflict_do_update(
                constraint="user_id_key_unique",
                set_={
                    "value": payload.value,
                    "confidence": 1.0,
                    "last_reinforced_at": func.now(),
                    "stale": False,
                },
            )
            .returning(ProceduralMemory)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        row = result.scalar_one()
        return ProceduralMemoryOut.model_validate(row)

    async def get(self, key: str) -> ProceduralMemoryOut | None:
        """Lee una entrada por ``key`` del usuario del store. ``None`` si no existe."""
        stmt = select(ProceduralMemory).where(
            ProceduralMemory.user_id == self._user_id,
            ProceduralMemory.key == key,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return ProceduralMemoryOut.model_validate(row) if row is not None else None

    async def update(self, key: str, value: dict[str, Any]) -> ProceduralMemoryOut | None:
        """Reemplaza el ``value`` (JSONB) de una entrada EXISTENTE por ``key``.

        Update PURO (no upsert): el WHERE filtra por ``user_id`` **y** ``key``; si la
        key no existe o pertenece a otro usuario, ``RETURNING`` viene vacío y se
        devuelve ``None`` (el endpoint lo mapea a 404). NUNCA crea la fila — editar
        vía ``PATCH`` algo inexistente debe ser 404, no un insert silencioso.

        A diferencia de ``upsert``, **no** resetea el decay (``confidence`` /
        ``stale`` / ``last_reinforced_at`` quedan intactos): editar a mano el valor
        de una preferencia no es una señal de refuerzo (ADR-007 D1), así que su
        estado de decay se preserva. El ``updated_at`` lo refresca el ORM
        (``TimestampMixin``).
        """
        stmt = (
            sa_update(ProceduralMemory)
            .where(
                ProceduralMemory.user_id == self._user_id,
                ProceduralMemory.key == key,
            )
            .values(value=value)
            .returning(ProceduralMemory)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        await self._session.flush()
        if row is None:
            return None
        return ProceduralMemoryOut.model_validate(row)

    async def list_all(self) -> list[ProceduralMemoryOut]:
        """Lista todas las entradas procedurales del usuario, ordenadas por ``key``."""
        stmt = (
            select(ProceduralMemory)
            .where(ProceduralMemory.user_id == self._user_id)
            .order_by(ProceduralMemory.key)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [ProceduralMemoryOut.model_validate(row) for row in rows]

    async def count(self) -> int:
        """Cuenta las entradas procedurales del usuario. No descifra (no hay cifrado acá).

        Espeja ``SemanticMemoryStore.count`` / ``EpisodicMemoryStore.count``: un
        ``SELECT count(*)`` filtrado por ``self._user_id`` (aislamiento estructural). Lo usa
        el preview del wipe (``GET /v1/memory/wipe``) para reportar el conteo de esta capa sin
        materializar las filas. La procedural no tenía ``count`` propio (su paginación se
        recortaba en Python sobre ``list_all``); el wipe lo necesita per-capa, así que se
        agrega de forma aditiva.
        """
        stmt = (
            select(func.count())
            .select_from(ProceduralMemory)
            .where(ProceduralMemory.user_id == self._user_id)
        )
        return (await self._session.execute(stmt)).scalar_one()

    async def delete(self, key: str) -> bool:
        """Borra físicamente una entrada por ``key``. ``True`` si borró una fila."""
        stmt = (
            sa_delete(ProceduralMemory)
            .where(
                ProceduralMemory.user_id == self._user_id,
                ProceduralMemory.key == key,
            )
            .returning(ProceduralMemory.id)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one_or_none() is not None

    async def wipe(self) -> int:
        """Hard-delete físico de TODAS las entradas procedurales del usuario. Devuelve el rowcount.

        Espejo de ``SemanticMemoryStore.wipe`` / ``EpisodicMemoryStore.wipe`` para la capa
        procedural (operación SAGRADA + DESTRUCTIVA + irreversible). El ``WHERE`` es
        ``user_id == self._user_id`` a secas (sin ``key``): barre el estado presente COMPLETO
        de este usuario en ``procedural_memory`` (aislamiento estructural: el ``user_id`` se
        ligó en el ``__init__`` y nunca toca otro usuario). La procedural no tiene cifrado ni
        embeddings, así que el borrado es directo.

        Usa ``rowcount`` —no ``RETURNING id`` + ``len``— porque es un bulk delete y ningún id
        se usa downstream; el ``rowcount`` es el número REAL de filas borradas (puede diferir
        de un conteo previo si el worker insertó en el ínterin; ese número siempre es verdad).

        Solo hace ``flush``: el ``commit`` lo da el endpoint en el happy path, en la MISMA
        transacción donde recontó (atomicidad recount+wipe+commit).
        """
        stmt = sa_delete(ProceduralMemory).where(ProceduralMemory.user_id == self._user_id)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount
