"""Store por-request de los device tokens del usuario (``device_tokens``, PR-B).

Espejo de ``TaskStore`` / ``CalendarEventStore``: el ``user_id`` se liga en el
``__init__`` y **todo** query del CRUD filtra por ``self._user_id`` (aislamiento
estructural). La EXCEPCIÓN deliberada es el upsert por token: ``register`` busca un token
EXISTENTE sin filtrar por user (el ``token`` es UNIQUE global), porque el mismo
dispositivo puede re-registrarse bajo otra cuenta y debe RE-ASIGNARSE, no duplicarse.

Operaciones:

- ``register(payload)``: upsert por ``token``. Si el token existe (de cualquier user),
  re-asigna ``user_id`` + ``platform`` + ``last_seen_at`` al store actual; si no,
  INSERTA. ``flush`` (no commit).
- ``unregister(token)``: borra el token SOLO si es del user (aislamiento). ``False`` si
  es ajeno / inexistente (el router lo traduce a 404 sin oráculo). ``flush``.
- ``list_for_user()``: los device tokens del user (para el scheduler de recordatorios y
  el listado). Filtra por ``user_id``.

Privacidad (regla #4): el ``token`` NUNCA se loguea acá; ``_to_result`` no expone
``user_id``.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device_token import DeviceToken
from app.schemas.device import DeviceRegister, DeviceTokenOut

logger = logging.getLogger(__name__)

# Cap de device tokens por usuario: cota anti-DoS de la tabla (un cliente comprometido no
# puede inflar ``device_tokens`` sin límite registrando tokens nuevos). 20 es holgado para
# los dispositivos reales de una persona (móvil + tablet + varios navegadores). SOLO aplica
# al INSERTAR un token NUEVO: un upsert de uno ya existente (re-registro/re-asignación) no
# cuenta contra el cap.
MAX_DEVICE_TOKENS_PER_USER = 20


class TooManyDeviceTokensError(Exception):
    """El usuario alcanzó ``MAX_DEVICE_TOKENS_PER_USER`` y quiso registrar uno NUEVO.

    Dominio (no HTTP): ``DeviceTokenStore.register`` la levanta; el router
    (``app/api/v1/devices.py``) la traduce a un 429 con ``detail`` genérico (regla #4: sin
    datos del usuario). Un upsert de un token existente NO la dispara.
    """


class DeviceTokenStore:
    """Store por-request de ``device_tokens``, ligado a un ``user_id``."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    async def register(self, payload: DeviceRegister) -> tuple[dict[str, object], bool]:
        """Upsert de un device token por ``token``. Devuelve ``(dict, created)``.

        El ``token`` es UNIQUE global: si ya existe (de ESTE u OTRO usuario), se RE-ASIGNA
        al user del store (``user_id`` + ``platform`` + ``last_seen_at`` frescos) en vez de
        insertar otra fila (que violaría el UNIQUE). Si no existe, INSERTA. Solo ``flush``:
        el commit lo da el router.

        Re-asignar un token ajeno es el comportamiento correcto: significa que el mismo
        dispositivo físico ahora pertenece a esta cuenta (reinstaló / cambió de login), así
        que sus pushes deben ir al nuevo dueño.

        ``created`` es ``True`` solo cuando se INSERTÓ una fila nueva (``False`` en el
        upsert): el router lo usa para el 201 vs 200 sin un read previo (cierra el TOCTOU
        cosmético de decidir el status code con ``list_for_user``).

        Cap: un token NUEVO cuenta contra ``MAX_DEVICE_TOKENS_PER_USER``; si el usuario ya
        está en el cap se levanta ``TooManyDeviceTokensError`` (→ 429 en el router). El
        upsert de un token existente NO cuenta contra el cap (no agrega filas).
        """
        existing = await self._find_by_token(payload.token)
        if existing is not None:
            if existing.user_id != self._user_id:
                # Re-asignación entre usuarios: rastro de auditoría con SOLO ids (regla #4:
                # NUNCA el token, que es una credencial). ``existing.id`` es el de la fila,
                # ``existing.user_id`` el dueño VIEJO, ``self._user_id`` el NUEVO.
                logger.info(
                    "device token reassigned: id=%s from_user=%s to_user=%s",
                    existing.id,
                    existing.user_id,
                    self._user_id,
                )
            existing.user_id = self._user_id
            existing.platform = payload.platform
            existing.last_seen_at = func.now()
            await self._session.flush()
            await self._session.refresh(existing)
            return self._to_result(existing), False

        # Token NUEVO: aplica el cap por usuario (un upsert ya retornó arriba sin contar).
        if await self._count_for_user() >= MAX_DEVICE_TOKENS_PER_USER:
            raise TooManyDeviceTokensError

        device = DeviceToken(
            user_id=self._user_id,
            platform=payload.platform,
            token=payload.token,
        )
        self._session.add(device)
        await self._session.flush()
        await self._session.refresh(device)
        return self._to_result(device), True

    async def _count_for_user(self) -> int:
        """Cuenta los device tokens del usuario (para el cap del ``register``).

        Filtra por ``self._user_id`` (aislamiento estructural). Lo usa ``register`` ANTES de
        insertar un token nuevo para no exceder ``MAX_DEVICE_TOKENS_PER_USER``.
        """
        return (
            await self._session.scalar(
                select(func.count())
                .select_from(DeviceToken)
                .where(DeviceToken.user_id == self._user_id)
            )
        ) or 0

    async def unregister(self, token: str) -> bool:
        """Borra un device token del usuario; ``True`` si existía, ``False`` si ajeno/inexistente.

        Filtra por ``self._user_id`` (aislamiento): un token de otro usuario es
        indistinguible de uno inexistente (el router traduce ``False`` a un 404 sin
        oráculo de existencia ajena). Solo ``flush``; el commit lo da el router.
        """
        device = await self._get_owned(token)
        if device is None:
            return False
        await self._session.delete(device)
        await self._session.flush()
        return True

    async def list_for_user(self) -> list[dict[str, object]]:
        """Lista los device tokens del usuario (orden ``last_seen_at`` DESC).

        Filtra por ``user_id`` (aislamiento). La usa el scheduler de recordatorios para
        cargar a quién despachar y el listado. Read-only.
        """
        stmt = (
            select(DeviceToken)
            .where(DeviceToken.user_id == self._user_id)
            .order_by(DeviceToken.last_seen_at.desc())
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [self._to_result(row) for row in rows]

    async def _get_owned(self, token: str) -> DeviceToken | None:
        """Devuelve el device token del usuario por ``token``, o ``None`` si ajeno/inexistente.

        Filtra por ``self._user_id`` (aislamiento estructural): un token de otro usuario es
        indistinguible de uno inexistente (sin oráculo de existencia ajena).
        """
        stmt = select(DeviceToken).where(
            DeviceToken.token == token, DeviceToken.user_id == self._user_id
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def _find_by_token(self, token: str) -> DeviceToken | None:
        """Devuelve la fila del ``token`` SIN filtrar por user (el token es UNIQUE global).

        Necesario para el upsert: un re-registro del mismo dispositivo (token ya en la
        tabla, posiblemente de OTRO user) debe RE-ASIGNARSE, no duplicarse. Es la única
        consulta del store que NO filtra por ``user_id`` (deliberado).
        """
        stmt = select(DeviceToken).where(DeviceToken.token == token)
        return (await self._session.execute(stmt)).scalars().first()

    @staticmethod
    def _to_result(row: DeviceToken) -> dict[str, object]:
        """Proyecta el ORM al dict serializable del wire (``DeviceTokenOut``).

        ``id`` + ``platform`` + ``token`` + ``last_seen_at``, SIN ``user_id`` /
        ``created_at`` / ``updated_at``. ``model_dump(mode="json")`` deja todo JSON-safe.
        """
        return DeviceTokenOut.model_validate(row).model_dump(mode="json")
