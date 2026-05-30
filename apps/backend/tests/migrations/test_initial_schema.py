"""Tests de la migracion inicial (PR B) — TABLAS SAGRADAS (regla #3).

Las pruebas que tocan la DB estan marcadas ``integration`` y se excluyen
del ``pytest`` default. Correrlas en AISLAMIENTO (la deuda de settings
no-lazy, issue #26, puede inyectar env dummy si se corre junto al suite
completo)::

    cd apps/backend && python -m pytest tests/migrations -m integration

Necesitan una DB Postgres real con pgvector (la MVP de Supabase via .env).
"""

from __future__ import annotations

import asyncio
import importlib.util
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


def _alembic_cfg() -> Config:
    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
    return cfg


async def _schema_snapshot() -> tuple[set[str], set[str], int]:
    from app.core.config import settings

    conn = await asyncpg.connect(dsn=settings.database_url.replace("+asyncpg", ""))
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
    """Integracion: upgrade crea el schema, downgrade lo borra, y deja la DB
    en head al final (estado esperado post-PR B)."""
    cfg = _alembic_cfg()

    command.upgrade(cfg, "head")
    tables, enums, vector = asyncio.run(_schema_snapshot())
    assert _TABLES <= tables, f"faltan tablas: {_TABLES - tables}"
    assert _ENUMS <= enums, f"faltan enums: {_ENUMS - enums}"
    assert vector == 1, "la extension vector no quedo instalada"

    command.downgrade(cfg, "base")
    tables_after, enums_after, _ = asyncio.run(_schema_snapshot())
    assert not (_TABLES & tables_after), "el downgrade no borro las tablas"
    assert not (_ENUMS & enums_after), "el downgrade no borro los enums"

    command.upgrade(cfg, "head")
