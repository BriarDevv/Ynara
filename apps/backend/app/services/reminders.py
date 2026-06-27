"""Store por-request de los recordatorios del usuario (``reminders``, PR-C).

Espejo de ``CalendarEventStore`` / ``TaskStore``: el ``user_id`` se liga en el
``__init__`` y **todo** query filtra por ``self._user_id`` (aislamiento estructural; el
``user_id`` nunca viaja como argumento de método). A diferencia de la memoria,
``reminders`` NO está cifrada (dominio operativo): el ``text`` se guarda en claro (pero
NUNCA se loguea — regla #4).

Operaciones:

- ``create_reminder(payload)``: alta IDEMPOTENTE para la **tool del agente** — deduplica
  por la tupla natural ``(user_id, text, remind_at)``; ``status`` arranca ``pending``.
  ``flush`` (no commit).
- ``add_reminder(payload)``: alta NO idempotente para el **POST REST** (un usuario que
  crea explícitamente espera que se cree). ``status`` ``pending``. ``flush``.
- ``list_window(from_dt, to_dt, *, limit)``: recordatorios en ``[from_dt, to_dt)`` por
  ``remind_at`` ASC — para el tool ``reminder.list`` (cap ``AGENT_LIST_RESULT_LIMIT``).
- ``list_all(*, limit, offset)``: todos los del user por ``remind_at`` ASC — para el GET.
- ``update_reminder(id, updates)`` / ``delete_reminder(id)``: edición/borrado por id con
  aislamiento (``None``/``False`` si ajeno/inexistente → 404 sin oráculo).

Solo hace ``flush`` (NO ``commit``): el commit lo da el caller (router HTTP / fixture).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ReminderStatus
from app.models.reminder import Reminder
from app.schemas.reminder import ReminderCreate, ReminderOut


class ReminderStore:
    """Store por-request de ``reminders``, ligado a un ``user_id``."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    async def create_reminder(self, payload: ReminderCreate) -> dict[str, object]:
        """Alta IDEMPOTENTE de un recordatorio (tool del agente) — dedup por tupla natural.

        Si ya existe un recordatorio del usuario con la misma tupla
        ``(text, remind_at)``, se devuelve ESE (sin INSERTAR otro): así un reintento de la
        pasada async del agente no crea el mismo aviso dos veces (ADR-021). ``status``
        arranca ``pending``. Solo ``flush``; el commit lo da el caller.
        """
        existing = await self._find_duplicate(text=payload.text, remind_at=payload.remind_at)
        if existing is not None:
            return self._to_result(existing)
        return await self._insert(payload)

    async def add_reminder(self, payload: ReminderCreate) -> dict[str, object]:
        """Alta NO idempotente (POST REST): INSERTA siempre, ``status`` ``pending``.

        Un usuario que crea explícitamente un recordatorio espera que se cree, aunque sea
        idéntico a otro. Solo ``flush``; el commit lo da el router.
        """
        return await self._insert(payload)

    async def _insert(self, payload: ReminderCreate) -> dict[str, object]:
        """INSERTA un recordatorio del usuario (``status=pending``) y devuelve el dict."""
        reminder = Reminder(
            user_id=self._user_id,
            text=payload.text,
            remind_at=payload.remind_at,
            status=ReminderStatus.PENDING,
        )
        self._session.add(reminder)
        await self._session.flush()
        await self._session.refresh(reminder)
        return self._to_result(reminder)

    async def list_window(
        self, from_dt: datetime, to_dt: datetime, *, limit: int | None = None
    ) -> list[dict[str, object]]:
        """Recordatorios PENDING del usuario que vencen en ``[from_dt, to_dt)``, ``remind_at`` ASC.

        Filtra por ``user_id``, ``status == pending`` **y** la ventana sobre ``remind_at``.
        El filtro de status es deliberado: esta es la consulta de la tool ``reminder.list``
        (ventana), que solo debe ver recordatorios ACTIVOS (un ``sent``/``cancelled`` mezclado
        confunde al agente). El CRUD HTTP usa ``list_all`` (muestra todos). Read-only.
        ``limit`` opcional (la tool pasa ``AGENT_LIST_RESULT_LIMIT`` para no volcar miles de
        filas al context del LLM).
        """
        stmt = (
            select(Reminder)
            .where(
                Reminder.user_id == self._user_id,
                Reminder.status == ReminderStatus.PENDING,
                Reminder.remind_at >= from_dt,
                Reminder.remind_at < to_dt,
            )
            .order_by(Reminder.remind_at.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [self._to_result(row) for row in rows]

    async def list_all(self, *, limit: int, offset: int) -> list[dict[str, object]]:
        """Todos los recordatorios del usuario (``remind_at`` ASC, paginado) — ``GET``.

        Filtra por ``user_id`` (aislamiento). Distinto de ``list_window`` (ventana de
        tiempo, tool del agente): el CRUD HTTP lista la cola completa del user.
        """
        stmt = (
            select(Reminder)
            .where(Reminder.user_id == self._user_id)
            .order_by(Reminder.remind_at.asc())
            .limit(limit)
            .offset(offset)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [self._to_result(row) for row in rows]

    async def update_reminder(
        self, reminder_id: UUID, updates: dict[str, object]
    ) -> dict[str, object] | None:
        """Update PARCIAL de un recordatorio del usuario; ``None`` si ajeno/inexistente.

        Aplica solo los campos de ``updates`` (ya filtrados con ``exclude_unset`` por el
        router). Filtra por ``self._user_id`` (aislamiento). Solo ``flush``.
        """
        reminder = await self._get_owned(reminder_id)
        if reminder is None:
            return None
        for field, value in updates.items():
            setattr(reminder, field, value)
        await self._session.flush()
        await self._session.refresh(reminder)
        return self._to_result(reminder)

    async def delete_reminder(self, reminder_id: UUID) -> bool:
        """Borra un recordatorio del usuario; ``True`` si existía, ``False`` si ajeno/inexistente.

        Filtra por ``self._user_id`` (aislamiento): el router traduce ``False`` a un 404
        sin oráculo de existencia ajena. Solo ``flush``; el commit lo da el router.
        """
        reminder = await self._get_owned(reminder_id)
        if reminder is None:
            return False
        await self._session.delete(reminder)
        await self._session.flush()
        return True

    async def _get_owned(self, reminder_id: UUID) -> Reminder | None:
        """Devuelve el recordatorio del usuario por id, o ``None`` si ajeno/inexistente.

        Filtra por ``self._user_id`` (aislamiento estructural): uno de otro usuario es
        indistinguible de uno inexistente (sin oráculo de existencia ajena).
        """
        stmt = select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == self._user_id)
        return (await self._session.execute(stmt)).scalars().first()

    async def _find_duplicate(self, *, text: str, remind_at: datetime) -> Reminder | None:
        """Devuelve un recordatorio del usuario con la misma tupla natural, o ``None``.

        La tupla ``(user_id, text, remind_at)`` identifica "el mismo aviso conversado": el
        dedupe que vuelve idempotente a ``create_reminder`` ante un reintento de la pasada
        async (ADR-021). Filtra por ``self._user_id`` (aislamiento estructural).
        """
        stmt = select(Reminder).where(
            Reminder.user_id == self._user_id,
            Reminder.text == text,
            Reminder.remind_at == remind_at,
        )
        return (await self._session.execute(stmt)).scalars().first()

    @staticmethod
    def _to_result(row: Reminder) -> dict[str, object]:
        """Proyecta el ORM al dict serializable del wire (``ReminderOut``).

        ``id`` + ``text`` + ``remind_at`` + ``status``, SIN ``user_id`` / ``created_at`` /
        ``updated_at``. ``model_dump(mode="json")`` deja todo JSON-safe (apto para el
        resultado de una tool, que se serializa con ``json.dumps`` en el tool loop).
        """
        return ReminderOut.model_validate(row).model_dump(mode="json")
