"""Tests de la migracion inicial (PR B) — TABLAS SAGRADAS (regla #3).

Dos niveles:

- **Unit (sin DB)**: ``test_migration_is_initial_and_well_formed`` (revision
  inicial + callables) y ``test_migration_declares_all_tables_and_enums``
  (parsea el source con ``ast`` y verifica que crea las 6 tablas y los 4
  enums). Corren siempre.
- **Integracion** (``integration``, excluido del run default): el roundtrip
  ``upgrade(head)`` / ``downgrade(base)``. Corre contra ``TEST_DATABASE_URL``
  (DB dedicada con pgvector, NUNCA prod: el downgrade DESTRUYE datos)::

      TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/ynara_test \\
          python -m pytest tests/migrations -m integration
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import os
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config

from alembic import command

_BACKEND = Path(__file__).resolve().parents[2]
_MIGRATION = _BACKEND / "alembic" / "versions" / "20260529_1949_initial_schema.py"

_TABLES = {
    "users",
    "sessions",
    "semantic_memory",
    "episodic_memory",
    "procedural_memory",
    "audit_log",
}
_ENUMS = {"mode_enum", "memory_layer_enum", "llm_model_enum", "audit_operation_enum"}


def test_migration_is_initial_and_well_formed() -> None:
    """Unit (sin DB): la inicial tiene down_revision None y upgrade/downgrade."""
    spec = importlib.util.spec_from_file_location("_initial_schema", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision is None
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_declares_all_tables_and_enums() -> None:
    """Unit (sin DB): el upgrade crea las 6 tablas sagradas y los 4 enums.

    Parsea el source con ``ast`` (no ejecuta SQL): recolecta los nombres de
    ``op.create_table(...)`` y el ``name=`` de cada ``postgresql.ENUM(...)``.
    Cubre el gap de que el unit test viejo solo miraba down_revision +
    callables, sin validar el contenido de la migracion.
    """
    tree = ast.parse(_MIGRATION.read_text(encoding="utf-8"))
    tables: set[str] = set()
    enums: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "create_table" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                tables.add(first.value)
        elif node.func.attr == "ENUM":
            for kw in node.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                    enums.add(kw.value.value)
    assert tables == _TABLES, f"tablas declaradas != esperadas: {tables ^ _TABLES}"
    assert enums == _ENUMS, f"enums declarados != esperados: {enums ^ _ENUMS}"


def _test_db_dsn() -> str:
    """DSN sync (para asyncpg) de la DB de tests. Vacio si no esta seteada.

    Usa ``TEST_DATABASE_URL`` — NUNCA ``settings.database_url`` (la MVP de
    Supabase): el roundtrip corre ``downgrade(base)``, que destruiria datos.
    """
    raw = os.environ.get("TEST_DATABASE_URL", "")
    return raw.replace("+asyncpg", "") if raw else ""


def _alembic_cfg() -> Config:
    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
    return cfg


async def _schema_snapshot(dsn: str) -> tuple[set[str], set[str], int]:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        tables = {
            r["tablename"]
            for r in await conn.fetch("select tablename from pg_tables where schemaname = 'public'")
        }
        enums = {
            r["typname"]
            for r in await conn.fetch("select typname from pg_type where typtype = 'e'")
        }
        vector = await conn.fetchval("select count(*) from pg_extension where extname = 'vector'")
        return tables, enums, vector
    finally:
        await conn.close()


@pytest.mark.integration
def test_upgrade_downgrade_roundtrip() -> None:
    """Integracion: upgrade crea el schema y downgrade lo borra (incl. vector).

    Corre contra ``TEST_DATABASE_URL`` (DB efimera dedicada). ``env.py`` toma
    esa misma env var, asi alembic apunta a la DB de tests y no a prod.
    """
    dsn = _test_db_dsn()
    if not dsn:
        pytest.skip("TEST_DATABASE_URL no seteada (DB de tests dedicada, NO prod)")
    cfg = _alembic_cfg()

    command.upgrade(cfg, "head")
    tables, enums, vector = asyncio.run(_schema_snapshot(dsn))
    assert _TABLES <= tables, f"faltan tablas: {_TABLES - tables}"
    assert _ENUMS <= enums, f"faltan enums: {_ENUMS - enums}"
    assert vector == 1, "la extension vector no quedo instalada"

    command.downgrade(cfg, "base")
    tables_after, enums_after, vector_after = asyncio.run(_schema_snapshot(dsn))
    assert not (_TABLES & tables_after), "el downgrade no borro las tablas"
    assert not (_ENUMS & enums_after), "el downgrade no borro los enums"
    assert vector_after == 0, "el downgrade no borro la extension vector"

    command.upgrade(cfg, "head")
