"""Tests de la migración ``reminders_table`` (PR-C).

Tabla OPERATIVA (no sagrada): ``reminders`` + enum ``reminder_status_enum`` + los 2
índices compuestos. Mismo patrón que ``test_device_tokens_migration.py``:

- **Unit (sin DB)**: la revisión encadena al head previo (``b2c3d4e5f6a7``) y declara la
  tabla + el enum + los índices compuestos (parseo del source con ``ast``).
- **Integración** (``integration``): roundtrip ``upgrade(head)`` / ``downgrade(<prev>)``
  en una DB EFÍMERA DEDICADA, verificando que la tabla, el enum y los índices se crean y
  se borran.
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
_MIGRATION = _BACKEND / "alembic" / "versions" / "20260625_1200_reminders_table.py"

_TABLE = "reminders"
_ENUM = "reminder_status_enum"
_INDEXES = {"ix_reminders_user_id_remind_at", "ix_reminders_status_remind_at"}
_NEW_REVISION = "c3d4e5f6a7b8"
_PREV_REVISION = "b2c3d4e5f6a7"  # device_tokens_table (head previo)


def test_migration_chains_to_previous_head() -> None:
    """Unit (sin DB): la revisión encadena al head previo y trae upgrade/downgrade."""
    spec = importlib.util.spec_from_file_location("_reminders_migration", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == _NEW_REVISION
    assert module.down_revision == _PREV_REVISION
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_declares_table_enum_and_indexes() -> None:
    """Unit (sin DB): el upgrade crea la tabla ``reminders``, el enum y los 2 compuestos."""
    tree = ast.parse(_MIGRATION.read_text(encoding="utf-8"))
    tables: set[str] = set()
    enums: set[str] = set()
    indexes: set[str] = set()

    def _index_name(arg: ast.expr) -> str | None:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
        # op.f("ix_...") => Call con el literal en args[0]
        if isinstance(arg, ast.Call) and arg.args and isinstance(arg.args[0], ast.Constant):
            return arg.args[0].value
        return None

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
        elif node.func.attr == "create_index" and node.args:
            name = _index_name(node.args[0])
            if name:
                indexes.add(name)
    assert _TABLE in tables
    assert _ENUM in enums
    assert _INDEXES <= indexes


def _test_db_dsn() -> str:
    raw = os.environ.get("TEST_DATABASE_URL", "")
    return raw.replace("+asyncpg", "") if raw else ""


def _alembic_cfg() -> Config:
    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
    return cfg


async def _table_enum_indexes(dsn: str) -> tuple[bool, bool, set[str]]:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        has_table = await conn.fetchval(
            "select count(*) from pg_tables where schemaname = 'public' and tablename = $1",
            _TABLE,
        )
        has_enum = await conn.fetchval(
            "select count(*) from pg_type where typtype = 'e' and typname = $1", _ENUM
        )
        rows = await conn.fetch(
            "select indexname from pg_indexes where schemaname = 'public' and tablename = $1",
            _TABLE,
        )
        return bool(has_table), bool(has_enum), {r["indexname"] for r in rows}
    finally:
        await conn.close()


_ROUNDTRIP_DB = "ynara_reminders_roundtrip"


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


@pytest.mark.integration
def test_upgrade_downgrade_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Integración: upgrade(head) crea tabla + enum + índices; downgrade(prev) los borra."""
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
        has_table, has_enum, indexes = asyncio.run(_table_enum_indexes(ephemeral_dsn))
        assert has_table, "reminders no quedó creada tras upgrade head"
        assert has_enum, "reminder_status_enum no quedó creado tras upgrade head"
        assert _INDEXES <= indexes, f"faltan índices compuestos: {_INDEXES - indexes}"

        command.downgrade(cfg, _PREV_REVISION)
        has_table_after, has_enum_after, _ = asyncio.run(_table_enum_indexes(ephemeral_dsn))
        assert not has_table_after, "el downgrade no borró reminders"
        assert not has_enum_after, "el downgrade no borró reminder_status_enum"
    finally:
        asyncio.run(_drop_db(maintenance_dsn, _ROUNDTRIP_DB))
