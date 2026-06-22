"""Store por-request de las tareas del usuario (``tasks``, Fase D1).

Espejo de ``CalendarEventStore`` (``app/calendar/store.py``) y de los stores de
memoria (``SemanticMemoryStore``): el ``user_id`` se liga en el ``__init__`` y
**todo** query filtra por ``self._user_id`` (aislamiento estructural; el ``user_id``
nunca viaja como argumento de método, así toda fila queda forzosamente atada al
usuario del store). A diferencia de la memoria, ``tasks`` NO está cifrada (es un
dominio operativo, no el moat sagrado): el ``title`` se guarda en claro.

Operaciones:

- ``create_task(payload)``: persiste una tarea (``status=pending``, igual que
  ``POST /v1/tasks``) y devuelve un **dict serializable** (no el ORM): el id + los
  campos del wire. IDEMPOTENTE (ver abajo): un re-run de la pasada async del agente
  con la misma tarea NO duplica filas.
- ``list_tasks()``: lista TODAS las tareas del usuario, pending primero y luego por
  ``scheduled_at`` ASC, como dicts serializables.
- ``set_status(task_id, status)``: togglea el estado de UNA tarea del usuario;
  devuelve el dict serializable, o ``None`` si la tarea no existe o es ajena (el
  caller HTTP traduce el ``None`` a un 404 sin oráculo).

IDEMPOTENCIA (ADR-021, invariante de la pasada async): ``create_task`` deduplica por
la tupla natural ``(user_id, title, scheduled_at)``. Si ya existe una tarea del
usuario con esos valores, se devuelve la existente en vez de INSERTAR otra. Esto
vuelve la tool idempotente ante un reintento de Celery (la pasada del agente vuelve
a correr el mismo turno → vuelve a emitir el mismo ``task.create_task`` → no crea la
tarea dos veces). El dedupe es la tupla "semánticamente el mismo to-do conversado";
dos to-dos legítimamente idénticos (mismo título y horario) colapsan en uno, que es
el comportamiento deseado para un re-anuncio del mismo pendiente. ``scheduled_at``
puede ser ``NULL``: el dedupe usa ``IS NULL`` cuando no hay horario (en SQL
``NULL = NULL`` es ``NULL``, no ``TRUE``, así que sin esto dos tareas sin horario no
deduplicarían).

Solo hace ``flush`` (NO ``commit``): el commit lo da el caller (el ``worker_session``
de la pasada async al salir del bloque, el router HTTP, o el fixture en tests), en la
misma transacción donde corre el tool loop.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import TaskStatus
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskOut


class TaskStore:
    """Store por-request de ``tasks``, ligado a un ``user_id``.

    El ``user_id`` se liga en el constructor: todo query filtra por
    ``self._user_id`` (aislamiento estructural, igual que ``CalendarEventStore`` y
    los stores de memoria).
    """

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    async def create_task(self, payload: TaskCreate) -> dict[str, object]:
        """Persiste una tarea del usuario (idempotente) y devuelve un dict serializable.

        El ``status`` arranca ``pending`` (igual que ``POST /v1/tasks``: no se acepta
        del payload).

        IDEMPOTENCIA: si ya existe una tarea del usuario con la misma tupla natural
        ``(title, scheduled_at)``, se devuelve ESA tarea (sin INSERTAR otra). Así un
        reintento de la pasada async del agente no crea el mismo to-do dos veces
        (ADR-021). Solo hace ``flush``: el commit lo da el caller.

        Returns:
            Dict serializable (JSON-safe) de la tarea: ``id`` + los campos del wire
            (``TaskOut``), nunca el objeto ORM ni ``user_id`` interno.
        """
        existing = await self._find_duplicate(
            title=payload.title,
            scheduled_at=payload.scheduled_at,
        )
        if existing is not None:
            return self._to_result(existing)

        task = Task(
            user_id=self._user_id,
            title=payload.title,
            status=TaskStatus.PENDING,
            scheduled_at=payload.scheduled_at,
            duration_min=payload.duration_min,
        )
        self._session.add(task)
        await self._session.flush()
        await self._session.refresh(task)
        return self._to_result(task)

    async def list_tasks(self) -> list[dict[str, object]]:
        """Lista TODAS las tareas del usuario, pending primero y luego por horario ASC.

        Filtra por ``user_id`` (aislamiento). Orden sensato para el dashboard "Hoy":
        las pendientes arriba (lo que falta hacer), y dentro de cada grupo por
        ``scheduled_at`` ASC (la próxima primero; las sin horario al final, porque
        ``NULL`` ordena último con ``nulls_last``). Read-only (no muta nada).

        Returns:
            Lista de dicts serializables (``TaskOut``), una por tarea.
        """
        stmt = (
            select(Task)
            .where(Task.user_id == self._user_id)
            .order_by(
                # pending (estado del enum) antes que done: comparamos contra el
                # valor pending para que el bool ordene pending=False primero.
                (Task.status != TaskStatus.PENDING),
                Task.scheduled_at.asc().nulls_last(),
            )
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [self._to_result(row) for row in rows]

    async def set_status(self, task_id: UUID, status: TaskStatus) -> dict[str, object] | None:
        """Setea el ``status`` de UNA tarea del usuario; devuelve el dict o ``None``.

        Busca la tarea por id Y ``user_id`` (aislamiento estructural: jamás matchea la
        de otro usuario). Si no existe o es ajena, devuelve ``None`` (el caller HTTP lo
        traduce a un 404 sin oráculo). Si existe, le fija el ``status`` y devuelve el
        dict serializable. Solo hace ``flush``: el commit lo da el caller.

        Returns:
            El dict serializable (``TaskOut``) de la tarea actualizada, o ``None`` si
            no existe / es de otro usuario.
        """
        task = await self._get_owned(task_id)
        if task is None:
            return None
        task.status = status
        await self._session.flush()
        await self._session.refresh(task)
        return self._to_result(task)

    async def _get_owned(self, task_id: UUID) -> Task | None:
        """Devuelve la tarea del usuario por id, o ``None`` si no existe / es ajena.

        Filtra por ``self._user_id`` (aislamiento estructural): una tarea de otro
        usuario es indistinguible de una inexistente (sin oráculo de existencia).
        """
        stmt = select(Task).where(Task.id == task_id, Task.user_id == self._user_id)
        return (await self._session.execute(stmt)).scalars().first()

    async def _find_duplicate(self, *, title: str, scheduled_at: object) -> Task | None:
        """Devuelve una tarea del usuario con la misma tupla natural, o ``None``.

        La tupla ``(user_id, title, scheduled_at)`` identifica "el mismo to-do
        conversado": el dedupe que vuelve idempotente a ``create_task`` ante un
        reintento de la pasada async (ADR-021). Filtra por ``self._user_id``
        (aislamiento estructural): jamás matchea la tarea de otro usuario.

        ``scheduled_at`` es nullable: cuando es ``None`` se compara con ``IS NULL``
        (en SQL ``NULL = NULL`` da ``NULL``, no ``TRUE``, así que sin esta rama dos
        tareas sin horario nunca deduplicarían).
        """
        stmt = select(Task).where(
            Task.user_id == self._user_id,
            Task.title == title,
        )
        if scheduled_at is None:
            stmt = stmt.where(Task.scheduled_at.is_(None))
        else:
            stmt = stmt.where(Task.scheduled_at == scheduled_at)
        return (await self._session.execute(stmt)).scalars().first()

    @staticmethod
    def _to_result(row: Task) -> dict[str, object]:
        """Proyecta el ORM al dict serializable del wire (``TaskOut``).

        Devuelve el shape que ve el modelo / el caller: ``id`` + campos de la tarea,
        SIN ``user_id`` / ``created_at`` / ``updated_at`` (mismo contrato que
        ``TaskOut``, que no los expone). ``model_dump(mode="json")`` deja todo
        JSON-safe (UUID → str, datetime → ISO), apto para el resultado de una tool
        (que se serializa con ``json.dumps`` en el tool loop).
        """
        return TaskOut.model_validate(row).model_dump(mode="json")
