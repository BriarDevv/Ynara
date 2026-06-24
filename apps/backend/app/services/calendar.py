"""Store por-request de la agenda del usuario (``calendar_events``, ADR-023).

Espejo de los stores operativos (``ConversationTurnStore``) y de memoria
(``SemanticMemoryStore``): el ``user_id`` se liga en el ``__init__`` y **todo**
query filtra por ``self._user_id`` (aislamiento estructural; el ``user_id`` nunca
viaja como argumento de método, así toda fila queda forzosamente atada al usuario
del store). A diferencia de la memoria, ``calendar_events`` NO está cifrada (es un
dominio operativo, no el moat sagrado): el ``content`` se guarda en claro.

Operaciones:

- ``create_event(payload)``: persiste un evento (``status=confirmed``, igual que
  ``POST /v1/events``) y devuelve un **dict serializable** (no el ORM): el id +
  los campos del wire. IDEMPOTENTE (ver abajo): un re-run de la pasada async del
  agente con el mismo evento NO duplica filas.
- ``list_events(from_dt, to_dt)``: lista los eventos del usuario que arrancan en
  ``[from_dt, to_dt)``, ordenados por ``start_at`` ASC, como dicts serializables.

IDEMPOTENCIA (ADR-021, invariante de la pasada async): ``create_event`` deduplica
por la tupla natural ``(user_id, title, start_at, duration_min)``. Si ya existe un
evento del usuario con esos cuatro valores, se devuelve el existente en vez de
INSERTAR otro. Esto vuelve la tool idempotente ante un reintento de Celery (la
pasada del agente vuelve a correr el mismo turno → vuelve a emitir el mismo
``calendar.create_event`` → no agenda el evento dos veces). El dedupe es la tupla
"semánticamente la misma cita"; dos citas legítimamente idénticas (mismo título,
inicio y duración) colapsan en una, que es el comportamiento deseado para un
re-anuncio del mismo plan conversado.

Solo hace ``flush`` (NO ``commit``): el commit lo da el caller (el
``worker_session`` de la pasada async al salir del bloque, o el fixture en tests),
en la misma transacción donde corre el tool loop.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus
from app.models.calendar_event import CalendarEvent
from app.schemas.calendar_event import CalendarEventOut, EventCreate


class RecurrenceNeedsTimeZoneError(ValueError):
    """Invariante ADR-023 violada sobre el estado MERGEADO de un evento.

    ``recurrence`` no vacía sin ``time_zone`` (la invariante que ``EventPatch`` no puede
    validar sola por ser parcial). Es un error de DOMINIO, NO HTTP: lo lanza
    ``CalendarEventStore.update_event`` y el router (``app/api/v1/events.py``) lo mapea a
    un 422 — así el store framework-free no necesita conocer ``HTTPException``.
    """


class CalendarEventStore:
    """Store por-request de ``calendar_events``, ligado a un ``user_id``.

    El ``user_id`` se liga en el constructor: todo query filtra por
    ``self._user_id`` (aislamiento estructural, igual que los stores de memoria y
    ``ConversationTurnStore``).
    """

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    async def create_event(self, payload: EventCreate) -> dict[str, object]:
        """Persiste un evento del usuario (idempotente) y devuelve un dict serializable.

        El ``status`` arranca ``confirmed`` (igual que ``POST /v1/events``: no se
        acepta del payload). La invariante ADR-023 (``recurrence`` exige
        ``time_zone``) ya la valida ``EventCreate`` antes de llegar acá.

        IDEMPOTENCIA: si ya existe un evento del usuario con la misma tupla natural
        ``(title, start_at, duration_min)``, se devuelve ESE evento (sin INSERTAR
        otro). Así un reintento de la pasada async del agente no agenda el mismo
        evento dos veces (ADR-021). Solo hace ``flush``: el commit lo da el caller.

        Returns:
            Dict serializable (JSON-safe) del evento: ``id`` + los campos del wire
            (``CalendarEventOut``), nunca el objeto ORM ni ``user_id`` interno.
        """
        existing = await self._find_duplicate(
            title=payload.title,
            start_at=payload.start_at,
            duration_min=payload.duration_min,
        )
        if existing is not None:
            return self._to_result(existing)

        event = CalendarEvent(
            user_id=self._user_id,
            title=payload.title,
            start_at=payload.start_at,
            duration_min=payload.duration_min,
            mode=payload.mode,
            status=EventStatus.CONFIRMED,
            location=payload.location,
            time_zone=payload.time_zone,
            all_day=payload.all_day,
            recurrence=payload.recurrence,
        )
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(event)
        return self._to_result(event)

    async def list_events(
        self, from_dt: datetime, to_dt: datetime, *, limit: int | None = None
    ) -> list[dict[str, object]]:
        """Lista los eventos del usuario que arrancan en ``[from_dt, to_dt)``.

        Filtra por ``user_id`` **y** la ventana de tiempo sobre ``start_at``,
        ordenado por ``start_at`` ASC (el más próximo primero, igual que
        ``GET /v1/events``). Read-only (no muta nada).

        ``limit`` es un tope opcional de filas. ``None`` (default) preserva el
        comportamiento del CRUD HTTP (sin tope). La superficie del agente
        (``AgentListEventsTool``) pasa un cap acotado (``AGENT_LIST_RESULT_LIMIT``) para no
        volcar miles de eventos (ventana de tiempo ancha) al context window del LLM ni al
        payload del turno.

        Returns:
            Lista de dicts serializables (``CalendarEventOut``), uno por evento.
        """
        stmt = (
            select(CalendarEvent)
            .where(
                CalendarEvent.user_id == self._user_id,
                CalendarEvent.start_at >= from_dt,
                CalendarEvent.start_at < to_dt,
            )
            .order_by(CalendarEvent.start_at.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [self._to_result(row) for row in rows]

    # --- CRUD HTTP (GET/POST/PATCH/DELETE de /v1/events) ----------------------
    # A diferencia de create_event/list_events (superficie del AGENTE: dedup + ventana
    # de tiempo), estos métodos sirven el CRUD del dashboard: lista completa paginada,
    # alta NO idempotente (un usuario que crea explícitamente espera que se cree), y
    # get/update/delete por id con aislamiento por user (sin oráculo de existencia ajena).

    async def list_all(self, *, limit: int, offset: int) -> list[dict[str, object]]:
        """Lista TODOS los eventos del usuario (start_at ASC, paginado) para ``GET /v1/events``.

        Filtra por ``user_id`` (aislamiento). Distinto de ``list_events`` (ventana de
        tiempo, agente): el CRUD HTTP lista el calendario completo del user.
        """
        stmt = (
            select(CalendarEvent)
            .where(CalendarEvent.user_id == self._user_id)
            .order_by(CalendarEvent.start_at.asc())
            .limit(limit)
            .offset(offset)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [self._to_result(row) for row in rows]

    async def add_event(self, payload: EventCreate) -> dict[str, object]:
        """Inserta SIEMPRE un evento nuevo (NO deduplica) — el alta de ``POST /v1/events``.

        Un usuario que crea explícitamente un evento espera que se cree, aunque sea
        idéntico a otro. Distinto de ``create_event``, que deduplica para la idempotencia
        de la pasada async del agente (ADR-021). ``status`` arranca ``confirmed``; la
        invariante ADR-023 ya la valida ``EventCreate``. Solo ``flush``; commit del router.
        """
        event = CalendarEvent(
            user_id=self._user_id,
            title=payload.title,
            start_at=payload.start_at,
            duration_min=payload.duration_min,
            mode=payload.mode,
            status=EventStatus.CONFIRMED,
            location=payload.location,
            time_zone=payload.time_zone,
            all_day=payload.all_day,
            recurrence=payload.recurrence,
        )
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(event)
        return self._to_result(event)

    async def update_event(
        self, event_id: UUID, updates: dict[str, object]
    ) -> dict[str, object] | None:
        """Update PARCIAL de un evento del usuario; ``None`` si ajeno/inexistente.

        Aplica solo los campos de ``updates`` (ya filtrados con ``exclude_unset`` por el
        router). Enforcea la invariante ADR-023 sobre el estado MERGEADO: si tras el patch
        queda con ``recurrence`` no vacía sin ``time_zone``, lanza
        ``RecurrenceNeedsTimeZoneError`` (el router → 422, sin commit). Solo ``flush``.
        """
        event = await self._get_owned(event_id)
        if event is None:
            return None
        for field, value in updates.items():
            setattr(event, field, value)
        if event.recurrence and not event.time_zone:
            raise RecurrenceNeedsTimeZoneError
        await self._session.flush()
        await self._session.refresh(event)
        return self._to_result(event)

    async def delete_event(self, event_id: UUID) -> bool:
        """Borra un evento del usuario; ``True`` si existía, ``False`` si ajeno/inexistente.

        Filtra por ``self._user_id`` (aislamiento): el router traduce ``False`` a un 404
        sin oráculo de existencia ajena. Solo ``flush``; el commit lo da el router.
        """
        event = await self._get_owned(event_id)
        if event is None:
            return False
        await self._session.delete(event)
        await self._session.flush()
        return True

    async def _get_owned(self, event_id: UUID) -> CalendarEvent | None:
        """Devuelve el evento del usuario por id, o ``None`` si no existe / es ajeno.

        Filtra por ``self._user_id`` (aislamiento estructural): un evento de otro usuario
        es indistinguible de uno inexistente (sin oráculo de existencia ajena).
        """
        stmt = select(CalendarEvent).where(
            CalendarEvent.id == event_id, CalendarEvent.user_id == self._user_id
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def _find_duplicate(
        self, *, title: str, start_at: datetime, duration_min: int
    ) -> CalendarEvent | None:
        """Devuelve un evento del usuario con la misma tupla natural, o ``None``.

        La tupla ``(user_id, title, start_at, duration_min)`` identifica "la misma
        cita conversada": el dedupe que vuelve idempotente a ``create_event`` ante
        un reintento de la pasada async (ADR-021). Filtra por ``self._user_id``
        (aislamiento estructural): jamás matchea el evento de otro usuario.
        """
        stmt = select(CalendarEvent).where(
            CalendarEvent.user_id == self._user_id,
            CalendarEvent.title == title,
            CalendarEvent.start_at == start_at,
            CalendarEvent.duration_min == duration_min,
        )
        return (await self._session.execute(stmt)).scalars().first()

    @staticmethod
    def _to_result(row: CalendarEvent) -> dict[str, object]:
        """Proyecta el ORM al dict serializable del wire (``CalendarEventOut``).

        Devuelve el shape que ve el modelo / el caller: ``id`` + campos del evento,
        SIN ``user_id`` / ``created_at`` / ``updated_at`` (mismo contrato que
        ``CalendarEventOut``, que no los expone). ``model_dump(mode="json")`` deja
        todo JSON-safe (UUID → str, datetime → ISO), apto para el resultado de una
        tool (que se serializa con ``json.dumps`` en el tool loop).
        """
        return CalendarEventOut.model_validate(row).model_dump(mode="json")
