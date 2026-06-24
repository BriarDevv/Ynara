"""Guard de completitud de ``Base.metadata`` (regresión AR-01).

``alembic/env.py`` hace ``from app.models import Base`` (solo el paquete, sin
``app.main``). Si un modelo se define en ``app/models/`` pero NO se re-exporta en
``app/models/__init__.py``, su tabla NO se registra en ``Base.metadata`` al
importar el paquete → ``alembic revision --autogenerate`` propondría un
``op.drop_table(...)`` destructivo y ``alembic check`` reportaría drift falso.

El bug original: ``Task`` (``app/models/task.py``) estaba referenciado solo bajo
``if TYPE_CHECKING`` en ``user.py`` y ausente de ``__init__.py``. En el runtime de
la app ``Task`` se registraba por carga transitiva del router ``/v1/tasks``, así
que el bug quedaba enmascarado — pero Alembic, que importa SOLO ``app.models``,
nunca veía la tabla ``tasks``.

Este test reproduce EXACTAMENTE el import path de Alembic en un subproceso limpio
(sin el ``app.main`` que ``tests/conftest.py`` importa por autouse, que cargaría
los routers y enmascararía la regresión).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Toda tabla que la app usa en prod debe quedar registrada con SOLO
# ``import app.models`` (el path de ``alembic/env.py``).
EXPECTED_TABLES = frozenset(
    {
        "users",
        "sessions",
        "conversation_turns",
        "calendar_events",
        "tasks",
        "admin_audit",
        "audit_log",
        "semantic_memory",
        "episodic_memory",
        "procedural_memory",
    }
)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _tables_seen_importing_only_app_models() -> tuple[set[str], str]:
    """Tablas en ``Base.metadata`` tras ``import app.models`` en un proceso limpio.

    Corre en subproceso con ``cwd`` = raíz del backend para que ``app`` resuelva
    desde el filesystem (igual que Alembic), sin el conftest de pytest en juego.
    """
    code = (
        "import app.models  # noqa: F401\n"
        "from app.models.base import Base\n"
        "import json, sys\n"
        "sys.stdout.write(json.dumps(sorted(Base.metadata.tables)))\n"
    )
    # S603: subproceso controlado — `sys.executable` (el mismo intérprete) + código
    # literal sin input externo. No hay superficie de inyección.
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        cwd=str(_BACKEND_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"`import app.models` falló:\n{proc.stderr}"
    return set(json.loads(proc.stdout)), proc.stdout


def test_all_app_tables_registered_importing_only_app_models() -> None:
    """Importar ``app.models`` registra TODAS las tablas de prod en el metadata."""
    seen, _ = _tables_seen_importing_only_app_models()
    missing = EXPECTED_TABLES - seen
    assert not missing, (
        "Tablas no registradas en Base.metadata vía `import app.models` "
        f"(Alembic propondría drop_table): {sorted(missing)}. "
        "¿Falta re-exportar el modelo en app/models/__init__.py?"
    )


def test_tasks_table_specifically_registered() -> None:
    """Guard puntual de la regresión AR-01: la tabla ``tasks`` está presente."""
    seen, _ = _tables_seen_importing_only_app_models()
    assert "tasks" in seen
