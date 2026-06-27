"""Entrega de notificaciones push — Protocol + implementación noop (PR-B, D4).

Por ahora SOLO el contrato (``NotificationDelivery``) + un noop
(``NoopNotificationDelivery``): NO se cablea FCM/APNS ni ningún proveedor real. El
scheduler de recordatorios (``app/workflows/reminder_dispatch.py``) depende del
**Protocol** (inyección por arg), así que cuando exista un proveedor real basta agregar
otra implementación y devolverla en ``build_notifier()`` — sin tocar el scheduler.

Privacidad (regla #4): el notifier loguea SOLO ``len(tokens)`` (un conteo), NUNCA el
``text`` del recordatorio (contenido del usuario) ni los tokens (credenciales).
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

__all__ = [
    "NoopNotificationDelivery",
    "NotificationDelivery",
    "build_notifier",
]


@runtime_checkable
class NotificationDelivery(Protocol):
    """Contrato de entrega de notificaciones push.

    Una sola operación: enviar ``text`` a una lista de ``tokens``. Devuelve cuántos
    envíos se consideraron despachados (para que el caller loguee/contabilice). El
    ``text`` y los ``tokens`` NUNCA deben loguearse en una implementación (regla #4).
    """

    async def send_many(self, *, tokens: list[str], text: str) -> int:
        """Envía ``text`` a ``tokens``; devuelve la cantidad despachada."""
        ...


class NoopNotificationDelivery:
    """Entrega noop: no manda nada real, solo cuenta (sin proveedor cableado).

    Loguea SOLO ``len(tokens)`` (regla #4: ni el ``text`` ni los tokens). Devuelve el
    número de tokens como "despachados" para que el scheduler pueda marcar el
    recordatorio como enviado y loguear el conteo del lote.
    """

    async def send_many(self, *, tokens: list[str], text: str) -> int:
        # Regla #4: SOLO el conteo, jamás el text (contenido del usuario) ni los tokens
        # (credenciales). ``text`` está en la firma por contrato del Protocol; acá no se usa
        # (el noop no envía nada), pero se mantiene el nombre para satisfacer el Protocol.
        _ = text
        count = len(tokens)
        logger.info("NoopNotificationDelivery.send_many: tokens=%d (noop)", count)
        return count


def build_notifier() -> NotificationDelivery:
    """Devuelve la implementación de ``NotificationDelivery`` activa.

    Hoy SIEMPRE el noop (no hay proveedor real cableado). Punto único de construcción:
    cuando exista FCM/APNS se elige acá (p.ej. por settings/flag) sin tocar el scheduler,
    que depende solo del Protocol.
    """
    return NoopNotificationDelivery()
