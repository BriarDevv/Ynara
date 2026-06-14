"""Tests UNIT de la instancia de Celery (sin DB ni broker).

Validan dos cosas:

1. La politica de fiabilidad EXPLICITA en ``celery_app.conf`` (P0.3): los
   valores estan seteados a mano, no a defaults implicitos. El contrato
   relevante es AT-MOST-ONCE (``task_acks_late=False``) hasta el dedup de Ola 3.
2. Consistencia beat <-> registro: el ``task`` referenciado por cada entrada del
   ``beat_schedule`` MATCHEA un name realmente registrado en ``celery_app.tasks``
   por el decorador ``@celery_app.task(name=...)`` del workflow. Se importan los
   modulos de workflows para forzar el registro antes de assertear.
3. Robustez en IMPORT-TIME del beat (#211): ``_DECAY_INTERVAL_DAYS`` se calcula
   al importar el modulo via ``load_decay_config()``, que puede levantar
   ``MemoryConfigError`` (config ausente/invalido). El modulo lo envuelve en
   try/except con fallback al default literal (14) para que el worker NUNCA se
   tumbe al importar antes de registrar las tasks.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from datetime import timedelta

# Importar las tasks de workflows las REGISTRA en celery_app.tasks via el
# decorador @celery_app.task(name=...). Sin estos imports el registro estaria
# vacio y el assert de consistencia beat<->registro seria un falso negativo.
# Se importan los objetos task (no solo los modulos) para assertear su ``.name``
# real contra el name registrado y el referenciado por el beat.
from app.workers.celery_app import celery_app
from app.workflows.audit_retention import purge_audit_log
from app.workflows.consolidation import consolidate_session, consolidate_turn
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

    def test_consolidate_session_task_is_registered(self) -> None:
        """``consolidate_session`` (episodica, issue #209) esta registrada."""
        assert consolidate_session.name in celery_app.tasks
        assert consolidate_session.name == "workflows.consolidate_session"

    def test_purge_audit_log_task_is_registered(self) -> None:
        """``purge_audit_log`` (referenciada por el beat) esta registrada.

        El beat ``purge-audit-log-monthly`` apunta a ``workflows.purge_audit_log``;
        importar la task arriba fuerza su registro para que
        ``test_every_beat_task_is_registered`` sea valido aun corriendo este archivo
        de forma aislada (su modulo ``audit_retention`` no se importaba antes)."""
        assert purge_audit_log.name in celery_app.tasks
        assert purge_audit_log.name == "workflows.purge_audit_log"

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


class TestDecayIntervalImportTimeFallback:
    """``_DECAY_INTERVAL_DAYS`` resiste un config invalido/ausente en import-time."""

    def test_import_does_not_crash_and_falls_back_when_config_raises(self) -> None:
        """Importar ``celery_app`` con un config roto NO crashea: el beat cae a 14.

        El fallback corre en IMPORT-TIME, antes de registrar las tasks. Para
        ejercitarlo sin reload (que contaminaria el ``celery_app`` global que
        comparte el resto de la suite) se importa el modulo en un SUBPROCESO
        limpio con ``load_decay_config`` parcheado para tirar
        ``MemoryConfigError``. Si el try/except faltara, el import explotaria y
        el subproceso saldria con codigo != 0; ademas se verifica que el valor
        resultante es el default literal (14).
        """
        script = textwrap.dedent(
            """
            import app.memory.config as mem_config
            from app.memory.config import MemoryConfigError


            def _boom(*args, **kwargs):
                raise MemoryConfigError("config invalido a proposito")


            # Parchear ANTES de importar celery_app: el modulo llama
            # load_decay_config() en su cuerpo (import-time).
            mem_config.load_decay_config = _boom

            from app.workers import celery_app

            assert celery_app._DECAY_INTERVAL_DAYS == 14, celery_app._DECAY_INTERVAL_DAYS
            print("OK", celery_app._DECAY_INTERVAL_DAYS)
            """
        )
        result = subprocess.run(  # noqa: S603 -- input fijo: sys.executable + script hardcodeado, sin data externa
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            "el import de celery_app crasheo con config invalido "
            f"(stdout={result.stdout!r} stderr={result.stderr!r})"
        )
        assert "OK 14" in result.stdout

    def test_uses_config_value_on_happy_path(self) -> None:
        """Sin fallo, ``_DECAY_INTERVAL_DAYS`` viene del config real (14 por default)."""
        from app.workers.celery_app import _DECAY_INTERVAL_DAYS

        assert _DECAY_INTERVAL_DAYS == 14
