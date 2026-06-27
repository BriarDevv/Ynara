"""Guarda de registro de tasks Celery (regresión).

El worker registra una task SOLO si su módulo se importa al arrancar. El paquete
``app.workflows`` importa sus módulos de task en ``__init__`` justamente para eso
(ver su docstring). Si alguien agrega un módulo de task nuevo y se OLVIDA de sumarlo
a ese ``__init__``, el worker arranca SIN esa task: el chat la encola con ``.delay()``
y se pierde como ``Received unregistered task`` — un fallo silencioso que los tests
que llaman a la función directo NO detectan (este es el caso que dejó
``workflows.agent_turn_pass`` sin registrar tras la Fase E/D1).

Este test importa ``app.workflows`` (lo que dispara el registro) y verifica que TODAS
las tasks esperadas estén en ``celery_app.tasks`` por su ``name`` público (el mismo
string que viaja en el wire del broker). Al agregar una task nueva: sumá su ``name``
acá y el módulo al ``__init__`` del paquete.
"""

from __future__ import annotations

import app.workflows  # noqa: F401  (import con efecto: registra las @celery_app.task)
from app.workers.celery_app import celery_app

# Nombres públicos (``name=`` del decorador) de TODAS las tasks que el worker debe
# registrar. Es el contrato con el broker: lo que el productor encola con ``.delay()``.
_EXPECTED_TASK_NAMES = frozenset(
    {
        "workflows.consolidate_turn",
        "workflows.consolidate_session",
        "workflows.decay_procedural",
        "workflows.purge_audit_log",
        "workflows.purge_episodic_memory",
        "workflows.agent_turn_pass",
        "workflows.dispatch_due_reminders",
    }
)


def test_all_expected_tasks_registered() -> None:
    """Cada task esperada está registrada en el ``celery_app`` (si no, el worker la rechaza)."""
    registered = set(celery_app.tasks.keys())
    missing = _EXPECTED_TASK_NAMES - registered
    assert not missing, f"tasks no registradas (el worker las rechazaría): {sorted(missing)}"


def test_agent_turn_pass_registered() -> None:
    """La pasada async del agente DEBE seguir registrada aunque esté DORMANT (ADR-022).

    Bajo la config de modos actual nadie la encola (el chat ejecuta las tools síncronas),
    pero la task se mantiene registrada y funcional para una futura pasada de agente en
    modos gemma. Si dejara de registrarse y luego se reactivara el encolador, el worker
    rechazaría cada turno como ``Received unregistered task``. Este test lockea el
    registro (fuera de scope borrarla en este PR).
    """
    assert "workflows.agent_turn_pass" in celery_app.tasks
