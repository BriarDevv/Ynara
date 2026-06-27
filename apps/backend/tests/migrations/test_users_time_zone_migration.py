"""Tests de la migración ``users_time_zone`` (PR-A).

Tabla SENSIBLE (no sagrada): ``users``. Valida que:

- **Unit (sin DB)**: la revisión encadena al head previo (``c1d2e3f4a5b6``) y su
  ``upgrade`` agrega la columna ``time_zone`` (parseo del source con ``ast``).
- **Integración** (``integration``): round-trip ``upgrade(head)`` / ``downgrade(prev)``
  en una DB EFÍMERA DEDICADA, verificando que la columna aparece (vía
  ``information_schema.columns``) tras el upgrade y desaparece tras el downgrade.
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
_MIGRATION = _BACKEND / "alembic" / "versions" / "20260625_1000_users_time_zone.py"

_TABLE = "users"
_COLUMN = "time_zone"
_NEW_REVISION = "a7b1c2d3e4f5"
_PREV_REVISION = "c1d2e3f4a5b6"  # index_tasks_user_id_scheduled_at (head previo)


# ---------------------------------------------------------------------------
# Unit (sin DB)
# ---------------------------------------------------------------------------


def test_migration_chains_to_previous_head() -> None:
    """La revisión encadena al head previo y trae upgrade/downgrade."""
    spec = importlib.util.spec_from_file_location("_users_time_zone_migration", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == _NEW_REVISION
    assert module.down_revision == _PREV_REVISION
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_upgrade_adds_time_zone_column() -> None:
    """El ``upgrade`` agrega la columna ``time_zone`` a ``users`` (``op.add_column``)."""
    tree = ast.parse(_MIGRATION.read_text(encoding="utf-8"))
    added: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "add_column" and len(node.args) >= 2:
            table = node.args[0]
            col = node.args[1]
            # add_column("users", sa.Column("time_zone", ...))
            if (
                isinstance(table, ast.Constant)
                and isinstance(col, ast.Call)
                and col.args
                and isinstance(col.args[0], ast.Constant)
            ):
                added.add((table.value, col.args[0].value))
    assert (_TABLE, _COLUMN) in added


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


async def _column_present(dsn: str, table: str, column: str) -> bool:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        count = await conn.fetchval(
            "select count(*) from information_schema.columns "
            "where table_schema = 'public' and table_name = $1 and column_name = $2",
            table,
            column,
        )
        return bool(count)
    finally:
        await conn.close()


_ROUNDTRIP_DB = "ynara_users_time_zone_roundtrip"


@pytest.mark.integration
def test_upgrade_downgrade_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """upgrade(head) agrega la columna ``time_zone``; downgrade(prev) la revierte."""
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
        assert asyncio.run(_column_present(ephemeral_dsn, _TABLE, _COLUMN)), (
            "users.time_zone debería existir tras upgrade head"
        )

        command.downgrade(cfg, _PREV_REVISION)
        assert not asyncio.run(_column_present(ephemeral_dsn, _TABLE, _COLUMN)), (
            "el downgrade no borró users.time_zone"
        )
    finally:
        asyncio.run(_drop_db(maintenance_dsn, _ROUNDTRIP_DB))
