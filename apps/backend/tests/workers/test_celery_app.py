"""Tests UNIT de la instancia de Celery (sin DB ni broker).

Validan dos cosas:

1. La politica de fiabilidad EXPLICITA en ``celery_app.conf`` (P0.3): los
   valores estan seteados a mano, no a defaults implicitos. El contrato
   relevante es AT-MOST-ONCE (``task_acks_late=False``) hasta el dedup de Ola 3.
2. Consistencia beat <-> registro: el ``task`` referenciado por cada entrada del
   ``beat_schedule`` MATCHEA un name realmente registrado en ``celery_app.tasks``
   por el decorador ``@celery_app.task(name=...)`` del workflow. Se importan los
   modulos de workflows para forzar el registro antes de assertear.
"""

from __future__ import annotations

from datetime import timedelta

# Importar las tasks de workflows las REGISTRA en celery_app.tasks via el
# decorador @celery_app.task(name=...). Sin estos imports el registro estaria
# vacio y el assert de consistencia beat<->registro seria un falso negativo.
# Se importan los objetos task (no solo los modulos) para assertear su ``.name``
# real contra el name registrado y el referenciado por el beat.
from app.workers.celery_app import celery_app
from app.workflows.consolidation import consolidate_turn
from app.workflows.decay import decay_procedural


class TestReliabilityPolicy:
    """La politica de fiabilidad esta seteada EXPLICITA (no defaults implicitos)."""

    def test_at_most_once_acks_early(self) -> None:
        """``task_acks_late=False`` => ackear antes de ejecutar (at-most-once)."""
        assert celery_app.conf.task_acks_late is False

    def test_reject_on_worker_lost(self) -> None:
        """Una task en vuelo se rechaza si el worker muere (no queda zombie)."""
        assert celery_app.conf.task_reject_on_worker_lost is True

    def test_prefetch_multiplier_is_one(self) -> None:
        """Sin pipelining: un mensaje por worker a la vez (tasks pesadas)."""
        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_soft_time_limit(self) -> None:
        """Soft limit de 90s (lanza SoftTimeLimitExceeded)."""
        assert celery_app.conf.task_soft_time_limit == 90

    def test_hard_time_limit(self) -> None:
        """Hard limit de 120s (mata la task)."""
        assert celery_app.conf.task_time_limit == 120

    def test_visibility_timeout(self) -> None:
        """Visibility timeout (180s) > task_time_limit (120s): no re-entrega activa."""
        assert celery_app.conf.broker_transport_options["visibility_timeout"] == 180


class TestBeatScheduleConsistency:
    """Cada entrada del beat referencia un name REALMENTE registrado."""

    def test_decay_beat_task_is_registered(self) -> None:
        """El ``task`` del beat de decay matchea el name del @celery_app.task real."""
        entry = celery_app.conf.beat_schedule["decay-procedural-every-interval"]
        task_name = entry["task"]
        # El name del beat debe existir en el registro (lo puso el decorador).
        assert task_name in celery_app.tasks
        # Y debe ser exactamente el name real del decorador en app.workflows.decay,
        # leido del objeto task (no un string hardcodeado): si alguien renombra el
        # @task(name=...) sin tocar el beat, este assert se cae.
        assert task_name == decay_procedural.name

    def test_consolidate_task_is_registered(self) -> None:
        """``consolidate_turn`` (la otra task de la cola) tambien esta registrada."""
        assert consolidate_turn.name in celery_app.tasks
        assert consolidate_turn.name == "workflows.consolidate_turn"

    def test_every_beat_task_is_registered(self) -> None:
        """Generico: TODO ``task`` del beat_schedule existe en el registro real.

        Atrapa un beat que apunte a un name inexistente o tipeado mal (el beat
        encolaria una task que ningun worker puede ejecutar).
        """
        for entry in celery_app.conf.beat_schedule.values():
            assert entry["task"] in celery_app.tasks

    def test_decay_beat_cadence_is_interval(self) -> None:
        """La cadencia del beat de decay es por-intervalo (no diaria)."""
        entry = celery_app.conf.beat_schedule["decay-procedural-every-interval"]
        assert isinstance(entry["schedule"], timedelta)
        assert entry["schedule"].days >= 1
