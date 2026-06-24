"""Enums compartidos cross-domain de Ynara.

Convención: los enums que aparecen en columnas de DB y en payloads de API
(o en routing LLM) viven acá, no duplicados por dominio. Pydantic schemas
y modelos SQLAlchemy importan desde este archivo.

Ownership de tipos PostgreSQL: cada enum se materializa como tipo PG
nativo (``native_enum=True``). El nombre del tipo + su creación van
asignados a **una sola** declaración SQLAlchemy "dueña" (con
``create_type=True``, default). Cualquier otro modelo que reuse el
mismo enum debe pasar ``create_type=False`` para evitar duplicar la
creación en Alembic. La asignación dueño está documentada en cada
clase abajo.
"""

from __future__ import annotations

from enum import StrEnum


def enum_values(enum_cls: type[StrEnum]) -> list[str]:
    """``values_callable`` para las columnas ``Enum`` nativas de Postgres.

    Sin esto SQLAlchemy materializa el tipo PG usando los *nombres* de los
    miembros (``PRODUCTIVIDAD``), no sus ``.value`` (``productividad``). Eso
    rompería los inserts del ORM y divergiría de lo que habla la API (Pydantic
    serializa StrEnum por ``.value``) y de la tabla de ``docs/MODELS.md``.
    Cada ``Enum(...)`` del modelo pasa ``values_callable=enum_values``.
    """
    return [member.value for member in enum_cls]


class Mode(StrEnum):
    """Modos de Ynara. Ver ``ynara.config.json[modes]`` y ADR-002.

    Tipo PG ``mode_enum`` — dueño: ``ChatSession.mode`` en
    ``app/models/session.py`` (``create_type=True``). Otros consumidores
    (``AuditLog.origin_mode`` en ``app/models/audit.py``) usan
    ``create_type=False``. La migración inicial crea los 4 tipos enum
    explícitamente antes de cualquier tabla (``create_type=False`` en
    todas las columnas), así que el orden de las tablas no condiciona la
    creación del enum; las FK sí imponen ``users`` -> ``sessions`` ->
    ``episodic``/``semantic``.
    """

    PRODUCTIVIDAD = "productividad"
    ESTUDIO = "estudio"
    BIENESTAR = "bienestar"
    VIDA = "vida"
    MEMORIA = "memoria"


class MemoryLayer(StrEnum):
    """Capa de memoria. Ver ``docs/product/MEMORY.md`` y ADR-003.

    Tipo PG ``memory_layer_enum`` — dueño: ``AuditLog.target_layer`` en
    ``app/models/audit.py`` (único consumidor por ahora,
    ``create_type=True``).
    """

    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"


class LlmModel(StrEnum):
    """Modelo LLM que actuó como origen de una operación. Ver ADR-002.

    Tipo PG ``llm_model_enum`` — dueño: ``AuditLog.origin_model``
    (único consumidor por ahora, ``create_type=True``).
    """

    GEMMA = "gemma"
    QWEN = "qwen"


class AuditOperation(StrEnum):
    """Operaciones registradas en audit_log.

    Tipo PG ``audit_operation_enum`` — dueño: ``AuditLog.operation``
    (único consumidor por ahora, ``create_type=True``).
    """

    READ = "read"
    WRITE = "write"
    UPDATE = "update"
    DELETE = "delete"


class TurnRole(StrEnum):
    """Rol de un turno de conversación persistido en ``conversation_turns``.

    Tipo PG ``turn_role_enum`` — dueño: ``ConversationTurn.role`` en
    ``app/models/conversation_turn.py`` (único consumidor por ahora,
    ``create_type=True``). ``conversation_turns`` es una tabla OPERATIVA
    (buffer transitorio que se purga tras la consolidación episódica), no
    sagrada; pero su ``content`` viaja cifrado AES-256-GCM per-user igual que
    la memoria del moat (regla #4).
    """

    USER = "user"
    MODEL = "model"


class EventStatus(StrEnum):
    """Estado de un evento de agenda. Ver ``packages/shared-schemas/src/agenda.ts``
    y ADR-023.

    Tipo PG ``event_status_enum`` — dueño: ``CalendarEvent.status`` en
    ``app/models/calendar_event.py`` (único consumidor por ahora,
    ``create_type=True``). ``confirmed`` es el estado inicial; ``tentative`` =
    sin confirmar; ``cancelled`` se muestra tachado (el front no lo borra).
    """

    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class TaskStatus(StrEnum):
    """Estado de una tarea/prioridad del día. Ver
    ``packages/shared-schemas/src/today.ts`` (``TaskStatusSchema``) y el dominio
    TAREAS (Fase D1, espejo de Agenda/ADR-023).

    Tipo PG ``task_status_enum`` — dueño: ``Task.status`` en
    ``app/models/task.py`` (único consumidor por ahora, pero la migración lo crea
    explícitamente con ``create_type=False`` en la columna, mismo patrón que
    ``event_status_enum``). ``pending`` es el estado inicial que fija el server al
    crear; el ``PATCH`` togglea entre ``pending`` y ``done`` (el check del front).
    """

    PENDING = "pending"
    DONE = "done"
