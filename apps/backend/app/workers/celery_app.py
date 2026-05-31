"""Instancia de Celery + autodiscovery de tasks + beat schedule."""

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
    # TODO: ajustar visibilidad de timeout / retry según la tarea.
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

# Autodiscovery de tasks en app.workflows.*
# TODO: agregar los módulos cuando estén los workflows reales.
celery_app.autodiscover_tasks(packages=["app.workflows"])
