"""Worker de despacho de recordatorios vencidos (PR-C).

Scan GLOBAL por-tiempo (NO por-usuario, igual que ``purge_episodic_memory`` /
``purge_audit_log``): busca los recordatorios ``pending`` cuya hora ya llegó
(``remind_at <= now``) y los despacha vía el ``NotificationDelivery`` inyectado (hoy un
noop), marcándolos ``sent``.

Reglas (regla #3 de ``AGENTS.md`` + perímetro regla #4):

1. UPDATE de ``reminders.status`` (tabla OPERATIVA, no sagrada) + side-effect de envío
   (noop por ahora). Scan GLOBAL: ``WHERE status='pending' AND remind_at<=now``, servido
   por el índice ``ix_reminders_status_remind_at``.
2. NO toca el SCHEMA: opera sobre columnas existentes.
3. Para cada vencido carga los device tokens del DUEÑO
   (``DeviceTokenStore(session, reminder.user_id)``) y los pasa al notifier. El notifier
   loguea SOLO ``len(tokens)`` (regla #4: jamás el ``text`` ni los tokens).
4. Mismo patrón Celery que ``episodic_retention.py``: cuerpo ``_async_`` con ``session``
   inyectable para tests + engine ``NullPool`` en prod + ``try/except`` que NO tumba el
   worker + logs SOLO de conteos. El commit es POR recordatorio (despacho atómico, LOW-02),
   no por lote: el scan sigue por lotes pero cada SENT se confirma apenas se manda el aviso,
   así un fallo a mitad no re-despacha los ya enviados.
5. ``now`` y ``notifier`` inyectables (``notifier or build_notifier()``) para tests
   deterministas.

PREDICADO ``<=`` (no ``<``): un recordatorio exacto en su hora (``remind_at == now``) SÍ
se despacha (ya venció). Un recordatorio a futuro (``remind_at > now``) queda intacto.

CADENCIA (beat): cada minuto (``timedelta(minutes=1)``, ver ``celery_app.py``).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.enums import ReminderStatus
from app.models.reminder import Reminder
from app.services.devices import DeviceTokenStore
from app.services.notifications import NotificationDelivery, build_notifier
from app.workers.celery_app import celery_app
from app.workflows._engine import worker_session

logger = logging.getLogger(__name__)

# Filas por lote del scan (acota cuántos vencidos se traen por SELECT). El commit es por
# recordatorio (no por lote, LOW-02): el lote solo limita el fan-out de cada query; el
# progreso se preserva apenas se confirma cada SENT, así un kill por time-limit no pierde ni
# re-despacha lo ya enviado.
DISPATCH_BATCH_SIZE = 100


async def _async_dispatch_due_reminders(
    *,
    session: AsyncSession | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
    notifier: NotificationDelivery | None = None,
    batch_size: int = DISPATCH_BATCH_SIZE,
) -> int:
    """Despacha los recordatorios vencidos y los marca ``sent``. Retorna #despachados.

    Para cada vencido: carga los device tokens del dueño → ``notifier.send_many`` →
    ``status=sent``. ``now`` y ``notifier`` son inyectables (tests deterministas; default
    reloj real + noop). Si ``session`` se inyecta (tests) se usa directamente y NO se
    commitea (el fixture controla el rollback). Si es ``None`` (worker Celery en prod) se
    construye el engine con ``NullPool``, se commitea POR recordatorio (despacho atómico,
    LOW-02) y se dispone el engine.
    """
    current = now or datetime.now(UTC)
    notify = notifier or build_notifier()

    async def _run(db: AsyncSession, *, commit: bool) -> int:
        dispatched = 0
        while True:
            stmt = (
                select(Reminder)
                .where(
                    Reminder.status == ReminderStatus.PENDING,
                    Reminder.remind_at <= current,
                )
                .order_by(Reminder.remind_at.asc())
                .limit(batch_size)
            )
            due = list((await db.execute(stmt)).scalars().all())
            if not due:
                break
            for reminder in due:
                # Tokens del DUEÑO del recordatorio (no del store global): aislamiento.
                tokens = [
                    str(item["token"])
                    for item in await DeviceTokenStore(db, reminder.user_id).list_for_user()
                ]
                # El notifier loguea SOLO len(tokens) (regla #4): ni el text ni los tokens.
                await notify.send_many(tokens=tokens, text=reminder.text)
                reminder.status = ReminderStatus.SENT
                # Despacho ATÓMICO por fila (LOW-02): flush + commit POR recordatorio, no por
                # lote. Si el lote fallaba a mitad, el commit por lote podía re-marcar SENT y
                # re-despachar en el próximo scan los que YA se habían enviado; commitear cada
                # fila apenas se marca SENT acota el blast radius a, como mucho, un re-envío del
                # ÚNICO recordatorio en vuelo al momento del fallo (los previos quedan firmes).
                await db.flush()
                if commit:
                    await db.commit()
                dispatched += 1
        return dispatched

    if session is not None:
        # Modo test: sesión inyectada, NO commitear (rollback del fixture). El loop igual
        # termina (los vencidos pasan a SENT en el flush y dejan de matchear el WHERE).
        return await _run(session, commit=False)

    # Modo producción: engine NullPool efímero; commit POR recordatorio (el commit final de
    # worker_session queda no-op) y worker_session dispone el engine.
    cfg = settings or get_settings()
    async with worker_session(cfg) as db_session:
        return await _run(db_session, commit=True)


@celery_app.task(bind=True, name="workflows.dispatch_due_reminders")
def dispatch_due_reminders(self) -> None:  # bind=True, self no se usa (sin retry)
    """Task Celery: despacha los recordatorios vencidos (cada minuto vía beat).

    Job GLOBAL de mantenimiento, sin argumentos (despacha por tiempo, no por usuario). El
    cuerpo async corre con ``asyncio.run`` (worker prefork). Todo va en ``try/except``: un
    fallo NO tumba el worker y se loguea SOLO el conteo, SIN datos de usuario (regla #4).
    """
    try:
        dispatched = asyncio.run(_async_dispatch_due_reminders())
        logger.info("dispatch_due_reminders: dispatched=%d", dispatched)
    except Exception as exc:
        # Regla: el worker NUNCA muere por un fallo del despacho.
        # regla #4: logger.error (NO logger.exception): el traceback / str(exc) podría
        # arrastrar contenido de usuario a los logs. Se loguea solo el TIPO de excepción.
        logger.error(
            "dispatch_due_reminders: fallo al despachar recordatorios: %s (sin datos de usuario)",
            type(exc).__name__,
        )
