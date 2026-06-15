"""Tests UNIT del wrapper Celery ``purge_episodic_memory`` (sin DB).

El borrado real (SQL sobre la tabla sagrada) se cubre en
``tests/integration/test_episodic_retention.py``. Acá solo se verifica el contrato
del task wrapper: corre el cuerpo async y, ante CUALQUIER fallo, NO propaga (regla:
el worker nunca muere por un fallo de retention; el fallo se loguea sin datos de
usuario, regla #4). Mismo patrón que ``tests/workflows/test_decay.py``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.workflows.episodic_retention import purge_episodic_memory


class TestPurgeEpisodicTaskWrapper:
    """``purge_episodic_memory`` corre el cuerpo async y es fail-open."""

    def test_success_runs_async_and_returns_none(self) -> None:
        """Camino feliz: awaitea ``_async_purge_episodic`` y devuelve ``None``."""
        with patch(
            "app.workflows.episodic_retention._async_purge_episodic", new_callable=AsyncMock
        ) as mock_async:
            mock_async.return_value = (2, 3)
            assert purge_episodic_memory() is None
            mock_async.assert_awaited_once()

    def test_does_not_propagate_if_async_raises(self) -> None:
        """Si el cuerpo async tira, el task NO propaga (fail-open) y loguea el fallo."""
        with (
            patch(
                "app.workflows.episodic_retention._async_purge_episodic", new_callable=AsyncMock
            ) as mock_async,
            patch("app.workflows.episodic_retention.logger.exception") as mock_log,
        ):
            mock_async.side_effect = RuntimeError("DB caida")
            assert purge_episodic_memory() is None
            # El fallo se loguea (observabilidad): atrapa que alguien remueva el log.
            mock_log.assert_called_once()

    def test_does_not_propagate_if_asyncio_run_raises(self) -> None:
        """Si ``asyncio.run`` mismo tira, el task NO propaga (fail-open)."""
        with patch("app.workflows.episodic_retention.asyncio.run") as mock_run:
            mock_run.side_effect = ValueError("loop error")
            assert purge_episodic_memory() is None
