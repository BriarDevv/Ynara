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
from app.memory.config import MemoryConfigError, load_decay_config, load_retention_config

# Cadencia del decay procedural (M8 Ola 3, ADR-007 D1). Se lee del loader de
# ``ynara.config.json[memory]`` (#211) en vez de importarlo de
# ``app.workflows.decay`` para evitar el ciclo de import (ese modulo importa
# ``celery_app`` de aqui). ``load_decay_config()`` es default-safe cuando el
# bloque ``[memory]`` no trae el threshold (cae al default de ADR-007 D1), pero
# AUN puede levantar ``MemoryConfigError`` si ``ynara.config.json`` falta, no es
# JSON valido o trae un valor invalido. Como esto corre en IMPORT-TIME, una
# excepcion aca tumbaria el worker ANTES de registrar las tasks. Por eso se
# envuelve en try/except con fallback al default literal (14 dias): el job nunca
# tumba el worker por un config ausente/invalido (la red final del task Celery
# sigue siendo su propio try/except). El override del operador via config se
# pierde si el config es invalido, pero el beat arranca igual.
_DECAY_INTERVAL_DAYS_FALLBACK = 14
try:
    _DECAY_INTERVAL_DAYS = load_decay_config().decay_interval_days
except MemoryConfigError:
    _DECAY_INTERVAL_DAYS = _DECAY_INTERVAL_DAYS_FALLBACK

# Cadencia (en dias) del worker de retention episodica. Mismo patron default-safe
# que el decay: se lee de ``ynara.config.json[memory].episodic_retention_interval_days``
# (default 1 = diario, configurable) y, si el config rompe en import-time
# (MemoryConfigError), cae al literal de fallback para NO tumbar el worker antes de
# registrar las tasks (la red final sigue siendo el try/except del propio task).
_EPISODIC_RETENTION_INTERVAL_DAYS_FALLBACK = 1
try:
    _EPISODIC_RETENTION_INTERVAL_DAYS = load_retention_config().episodic_retention_interval_days
except MemoryConfigError:
    _EPISODIC_RETENTION_INTERVAL_DAYS = _EPISODIC_RETENTION_INTERVAL_DAYS_FALLBACK

# El singleton de Celery se construye al importar (lo necesitan worker y beat).
# get_settings() (lru_cache) se llama inline en los args en vez de capturar un
# `settings` a nivel de módulo (convención del repo: no instanciar Settings global);
# las dos llamadas devuelven el mismo objeto cacheado.
celery_app = Celery(
    "ynara",
    broker=get_settings().celery_broker_url,
    backend=get_settings().celery_result_backend,
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
    # ⚠️ INERTE HOY (early-ack / at-most-once): este flag NO da ninguna proteccion
    # de crash bajo la config actual. Solo surte efecto con task_acks_late=True
    # (Ola 3): recien ahi rechaza/reencola un mensaje AUN NO ackeado si el worker
    # muere. Con task_acks_late=False el mensaje YA se ackeo antes de ejecutar, asi
    # que no hay nada que reencolar. Se deja seteado SOLO como preparacion para
    # Ola 3; no asumir que protege contra worker-lost hoy.
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
    # Retention del audit_log: borra entradas > 24 meses (AUDIT_RETENTION_DAYS).
    # Cadencia mensual: para una retention de 24 meses no hace falta correr a
    # diario; mensual mantiene la tabla acotada sin scheduling innecesario.
    "purge-audit-log-monthly": {
        "task": "workflows.purge_audit_log",
        "schedule": timedelta(days=30),
    },
    # Retention episodica (ADR-007 D2 / roadmap §5.3): borra episodios cuya ventana
    # (created_at + retention_days) ya vencio. Cadencia config-driven (default 1 =
    # diario); a diferencia del audit (mensual, 24m de retention) los episodios
    # sensibles vencen a 180d, asi que conviene una cadencia mas fina y configurable.
    "purge-episodic-memory-every-interval": {
        "task": "workflows.purge_episodic_memory",
        "schedule": timedelta(days=_EPISODIC_RETENTION_INTERVAL_DAYS),
    },
}

# Autodiscovery de tasks en app.workflows.*. Hoy registra consolidation.py
# (consolidate_turn) y decay.py (decay_procedural); ambos ya existen. Los
# nuevos workflows que se agreguen al paquete se descubren solos.
celery_app.autodiscover_tasks(packages=["app.workflows"])
