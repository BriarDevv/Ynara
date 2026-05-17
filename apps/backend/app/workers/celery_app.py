"""Instancia de Celery + autodiscovery de tasks."""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

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

# Autodiscovery de tasks en app.workflows.*
# TODO: agregar los módulos cuando estén los workflows reales.
celery_app.autodiscover_tasks(packages=["app.workflows"])
