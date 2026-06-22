"""Dominio Agenda (operativo, NO sagrado): store por-request de ``calendar_events``.

Espeja la organización de ``app/memory/`` (un paquete por dominio con su store
ligado al ``user_id``), pero sobre la tabla OPERATIVA ``calendar_events`` (ADR-018).
NO vive bajo ``app/memory/`` a propósito: esa carpeta es la del moat sagrado
(regla #3, gate humano); la agenda es un dominio operativo aparte.

El store lo consume tanto el CRUD HTTP (``app/api/v1/events.py``, que hoy escribe
el modelo directo) como la pasada asíncrona del agente (ADR-021 / Fase E): cuando
qwen decide ``calendar.create_event`` por detrás de la conversación, la tool real
escribe acá vía ``CalendarEventStore``.
"""

from __future__ import annotations

from app.calendar.store import CalendarEventStore

__all__ = ["CalendarEventStore"]
