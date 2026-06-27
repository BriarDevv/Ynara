"""Modelo SQLAlchemy de device token para push: ``device_tokens``.

Tabla **OPERATIVA**, no sagrada (regla #3): guarda los tokens de push de los
dispositivos del usuario (FCM/APNS/web push). El scheduler de recordatorios
(``app/workflows/reminder_dispatch.py``) los carga para despachar avisos vía el
``NotificationDelivery`` (hoy un noop, sin proveedor real cableado).

Privacidad (regla #4): el ``token`` ES una credencial de envío (no PII directa, pero
sensible) — NUNCA viaja en URLs (el unregister va por body, no por path) ni se loguea
(el notifier loguea SOLO ``len(tokens)``, nunca el token). El ``DeviceTokenOut`` no
expone ``user_id``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import DevicePlatform, enum_values
from app.models.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.user import User


__all__ = ["DeviceToken"]


class DeviceToken(UUIDPKMixin, TimestampMixin, Base):
    """Un device token de push de un dispositivo del usuario.

    Un usuario tiene N device tokens (un dispositivo c/u). ``token`` es UNIQUE global:
    si el mismo dispositivo se re-registra (p.ej. tras reinstalar o cambiar de cuenta),
    el upsert re-asigna ``user_id`` + ``platform`` + ``last_seen_at`` en vez de duplicar
    la fila. ``last_seen_at`` marca el último registro/visto (para limpiar tokens
    muertos en una fase futura).
    """

    __tablename__ = "device_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # device_platform_enum es propio de esta tabla; la migración lo crea explícitamente
    # (como task_status_enum), así que la columna pasa create_type=False.
    platform: Mapped[DevicePlatform] = mapped_column(
        Enum(
            DevicePlatform,
            name="device_platform_enum",
            native_enum=True,
            values_callable=enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    # UNIQUE global: el mismo token (dispositivo) no se duplica entre usuarios; un
    # re-registro re-asigna el dueño. 512 chars cubre holgado FCM/APNS/web push.
    token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="device_tokens")
