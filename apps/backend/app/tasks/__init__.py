"""Dominio TAREAS (operativo, NO sagrado): store por-request de ``tasks``.

Espeja la organización de ``app/calendar/`` (un paquete por dominio con su store
ligado al ``user_id``), pero sobre la tabla OPERATIVA ``tasks`` (Fase D1, espejo de
Agenda/ADR-018). NO vive bajo ``app/memory/`` a propósito: esa carpeta es la del
moat sagrado (regla #3, gate humano); las tareas son un dominio operativo aparte.

El store lo consume tanto el CRUD HTTP (``app/api/v1/tasks.py``) como la pasada
asíncrona del agente (Fase E / ADR-021): cuando qwen decide ``task.create_task`` por
detrás de la conversación, la tool real escribe acá vía ``TaskStore``.
"""

from __future__ import annotations

from app.tasks.store import TaskStore

__all__ = ["TaskStore"]
