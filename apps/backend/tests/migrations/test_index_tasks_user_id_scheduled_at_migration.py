"""Tests de la migración ``index_tasks_user_id_scheduled_at`` (auditoría ALB-04).

Tabla OPERATIVA: ``tasks`` (no sagrada). Valida que:

- **Unit (sin DB)**: la revisión encadena al head previo (``b8e4f2a1c3d6``) y su
  ``upgrade`` crea el índice ``ix_tasks_user_id_scheduled_at`` (parseo del source con
  ``ast``).
- **Integración** (``integration``): round-trip ``upgrade(head)`` / ``downgrade(prev)``
  en una DB EFÍMERA DEDICADA, verificando que el índice aparece tras el upgrade y
  desaparece tras el downgrade.
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
from alembic.config import Config

from alembic import command

_BACKEND = Path(__file__).resolve().parents[2]
_MIGRATION = _BACKEND / "alembic" / "versions" / "20260624_1400_index_tasks_user_id_scheduled_at.py"

_NEW_REVISION = "c1d2e3f4a5b6"
_PREV_REVISION = "b8e4f2a1c3d6"  # index_memory_created_at (head previo)
_CREATED = {"ix_tasks_user_id_scheduled_at": "tasks"}


# ---------------------------------------------------------------------------
# Unit (sin DB)
# ---------------------------------------------------------------------------


def test_migration_chains_to_previous_head() -> None:
    """La revisión encadena a index_memory_created_at y trae upgrade/downgrade."""
    spec = importlib.util.spec_from_file_location("_index_tasks_user_id_scheduled_at", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == _NEW_REVISION
    assert module.down_revision == _PREV_REVISION
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_upgrade_creates_the_composite_index() -> None:
    """El ``upgrade`` crea ``ix_tasks_user_id_scheduled_at``."""
    tree = ast.parse(_MIGRATION.read_text(encoding="utf-8"))

    def _index_name(arg: ast.expr) -> str | None:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
        if isinstance(arg, ast.Call) and arg.args and isinstance(arg.args[0], ast.Constant):
            return arg.args[0].value
        return None

    created: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "create_index" and node.args:
            name = _index_name(node.args[0])
            if name:
                created.add(name)
    assert set(_CREATED) <= created


# ---------------------------------------------------------------------------
# Integración (DB efímera dedicada)
# ---------------------------------------------------------------------------


def _test_db_dsn() -> str:
    raw = os.environ.get("TEST_DATABASE_URL", "")
    return raw.replace("+asyncpg", "") if raw else ""


def _alembic_cfg() -> Config:
    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
    return cfg


def _swap_database(dsn: str, dbname: str) -> str:
    return urlunsplit(urlsplit(dsn)._replace(path=f"/{dbname}"))


async def _create_db(maintenance_dsn: str, name: str) -> None:
    conn = await asyncpg.connect(dsn=maintenance_dsn)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


async def _drop_db(maintenance_dsn: str, name: str) -> None:
    conn = await asyncpg.connect(dsn=maintenance_dsn)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    finally:
        await conn.close()


async def _index_names(dsn: str, table: str) -> set[str]:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        rows = await conn.fetch(
            "select indexname from pg_indexes where schemaname = 'public' and tablename = $1",
            table,
        )
        return {r["indexname"] for r in rows}
    finally:
        await conn.close()


_ROUNDTRIP_DB = "ynara_index_tasks_user_id_scheduled_at_roundtrip"


@pytest.mark.integration
def test_upgrade_downgrade_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """upgrade(head) crea el índice compuesto; downgrade(prev) lo revierte."""
    base_dsn = _test_db_dsn()
    if not base_dsn:
        pytest.skip("TEST_DATABASE_URL no seteada (DB de tests dedicada, NO prod)")

    maintenance_dsn = _swap_database(base_dsn, "postgres")
    ephemeral_dsn = _swap_database(base_dsn, _ROUNDTRIP_DB)

    asyncio.run(_create_db(maintenance_dsn, _ROUNDTRIP_DB))
    monkeypatch.setenv("TEST_DATABASE_URL", ephemeral_dsn)
    cfg = _alembic_cfg()
    try:
        command.upgrade(cfg, "head")
        for index, table in _CREATED.items():
            assert index in asyncio.run(_index_names(ephemeral_dsn, table)), (
                f"{index} debería existir en {table} tras upgrade head"
            )

        command.downgrade(cfg, _PREV_REVISION)
        for index, table in _CREATED.items():
            assert index not in asyncio.run(_index_names(ephemeral_dsn, table)), (
                f"el downgrade no borró {index} de {table}"
            )
    finally:
        asyncio.run(_drop_db(maintenance_dsn, _ROUNDTRIP_DB))
