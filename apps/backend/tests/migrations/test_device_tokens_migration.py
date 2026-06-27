"""Tests de la migración ``device_tokens_table`` (PR-B).

Tabla OPERATIVA (no sagrada): ``device_tokens`` + enum ``device_platform_enum``. Mismo
patrón que ``test_conversation_turns_migration.py``:

- **Unit (sin DB)**: la revisión encadena al head previo (``a7b1c2d3e4f5``) y declara la
  tabla + el enum (parseo del source con ``ast``).
- **Integración** (``integration``): roundtrip ``upgrade(head)`` / ``downgrade(<prev>)``
  en una DB EFÍMERA DEDICADA, verificando que la tabla y el enum se crean y se borran.
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
_MIGRATION = _BACKEND / "alembic" / "versions" / "20260625_1100_device_tokens_table.py"

_TABLE = "device_tokens"
_ENUM = "device_platform_enum"
_NEW_REVISION = "b2c3d4e5f6a7"
_PREV_REVISION = "a7b1c2d3e4f5"  # users_time_zone (head previo)


def test_migration_chains_to_previous_head() -> None:
    """Unit (sin DB): la revisión encadena al head previo y trae upgrade/downgrade."""
    spec = importlib.util.spec_from_file_location("_device_tokens_migration", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == _NEW_REVISION
    assert module.down_revision == _PREV_REVISION
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_declares_table_and_enum() -> None:
    """Unit (sin DB): el upgrade crea la tabla ``device_tokens`` y el enum."""
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
    assert _TABLE in tables
    assert _ENUM in enums


def _test_db_dsn() -> str:
    raw = os.environ.get("TEST_DATABASE_URL", "")
    return raw.replace("+asyncpg", "") if raw else ""


def _alembic_cfg() -> Config:
    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
    return cfg


async def _table_and_enum_present(dsn: str) -> tuple[bool, bool]:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        has_table = await conn.fetchval(
            "select count(*) from pg_tables where schemaname = 'public' and tablename = $1",
            _TABLE,
        )
        has_enum = await conn.fetchval(
            "select count(*) from pg_type where typtype = 'e' and typname = $1", _ENUM
        )
        return bool(has_table), bool(has_enum)
    finally:
        await conn.close()


_ROUNDTRIP_DB = "ynara_device_tokens_roundtrip"


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
    """Integración: upgrade(head) crea la tabla + enum; downgrade(prev) los borra."""
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
        has_table, has_enum = asyncio.run(_table_and_enum_present(ephemeral_dsn))
        assert has_table, "device_tokens no quedó creada tras upgrade head"
        assert has_enum, "device_platform_enum no quedó creado tras upgrade head"

        command.downgrade(cfg, _PREV_REVISION)
        has_table_after, has_enum_after = asyncio.run(_table_and_enum_present(ephemeral_dsn))
        assert not has_table_after, "el downgrade no borró device_tokens"
        assert not has_enum_after, "el downgrade no borró device_platform_enum"
    finally:
        asyncio.run(_drop_db(maintenance_dsn, _ROUNDTRIP_DB))
