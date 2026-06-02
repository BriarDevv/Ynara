"""Instancia de Celery + autodiscovery de tasks + beat schedule.

POLITICA DE FIABILIDAD (explicita, no defaults implicitos): la cola corre
tasks que escriben en tablas SAGRADAS (``consolidate_turn`` aplica ops via
``apply_ops``; ``decay_procedural`` hace UPDATE/DELETE sobre
``procedural_memory``). Por eso ``consolidate_turn`` es **AT-MOST-ONCE** hasta
tener dedup: con ``task_acks_late=False`` el broker ackea ANTES de ejecutar, asi
un crash del worker NO reencola y NO reejecuta. Esto evita el duplicado de
hechos que hoy produciria un reintento, porque ``apply_ops`` aplica ADD semantic
SIN dedup (search-before-add): reintentar el mismo turno insertaria el mismo
hecho otra vez. La idempotencia real de ``apply_ops`` (search-before-add que
hace el ADD semantic idempotente y habilita ``task_acks_late=True`` + retries)
es **Ola 3** y queda TRACKEADA — NO se implementa aca. Hasta entonces preferimos
perder una consolidacion ante un crash raro antes que duplicar memoria del
usuario silenciosamente.
"""

from __future__ import annotations

from datetime import timedelta

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

# Cadencia del decay procedural (M8 Ola 3, ADR-007 D1). Se inlinea el valor de
# ``DECAY_INTERVAL_DAYS`` en vez de importarlo de ``app.workflows.decay`` para
# evitar el ciclo de import (ese modulo importa ``celery_app`` de aqui). El
# valor canonico vive en ``app.workflows.decay.DECAY_INTERVAL_DAYS``.
_DECAY_INTERVAL_DAYS = 14

celery_app = Celery(
    "ynara",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Argentina/Buenos_Aires",
    enable_utc=True,
    task_track_started=True,
    # --- Politica de fiabilidad EXPLICITA (ver docstring del modulo) ---
    # AT-MOST-ONCE: ackear ANTES de ejecutar. Un crash NO reencola, asi
    # consolidate_turn (ADD semantic sin dedup) NO duplica hechos al reintentar.
    # task_acks_late=True + retries es Ola 3 (search-before-add idempotente).
    task_acks_late=False,
    # Solo surte efecto con task_acks_late=True (Ola 3): rechaza/reencola un mensaje
    # AUN NO ackeado si el worker muere. Bajo el at-most-once actual (early-ack) es
    # INERTE — el mensaje ya se ackeo antes de ejecutar. Se deja seteado como
    # preparacion para Ola 3; hoy NO da proteccion de crash por si mismo.
    task_reject_on_worker_lost=True,
    # Sin pipelining: un mensaje por worker a la vez (tasks pesadas, no rafagas).
    worker_prefetch_multiplier=1,
    # Limites de tiempo: soft (90s) lanza SoftTimeLimitExceeded; hard (120s) mata.
    task_soft_time_limit=90,
    task_time_limit=120,
    # Redis visibility_timeout. Con early-ack (acks_late=False) el mensaje se quita
    # de la cola al entregarlo, asi que hoy es mayormente INOCUO para estas tasks; el
    # techo 180s > task_time_limit (120s) solo importa el dia que Ola 3 pase a
    # task_acks_late=True, para no re-entregar una task que todavia corre.
    broker_transport_options={"visibility_timeout": 180},
)

# Beat schedule. El decay procedural corre cada DECAY_INTERVAL_DAYS dias, NO
# diario: la regla es "confidence *= 0.9 por intervalo" y sin una columna
# last_decayed_at (que seria migracion sagrada) la cadencia por-intervalo es la
# unica forma de evitar el compounding dia a dia. Cada corrida decae las
# entradas no reforzadas en el ultimo intervalo (ADR-007 D1, decision M8 Ola 3).
celery_app.conf.beat_schedule = {
    "decay-procedural-every-interval": {
        "task": "workflows.decay_procedural",
        "schedule": timedelta(days=_DECAY_INTERVAL_DAYS),
    },
}

# Autodiscovery de tasks en app.workflows.*. Hoy registra consolidation.py
# (consolidate_turn) y decay.py (decay_procedural); ambos ya existen. Los
# nuevos workflows que se agreguen al paquete se descubren solos.
celery_app.autodiscover_tasks(packages=["app.workflows"])
