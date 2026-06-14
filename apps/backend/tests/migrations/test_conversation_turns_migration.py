"""Tests de la migracion ``conversation_turns`` (issue #209).

Tabla OPERATIVA (no sagrada), pero su migracion vive bajo
``alembic/versions/`` y se valida igual que las demas:

- **Unit (sin DB)**: la revision encadena al head previo y declara la tabla +
  el enum ``turn_role_enum`` (parseo del source con ``ast``). Corren siempre.
- **Integracion** (``integration``): roundtrip ``upgrade(head)`` /
  ``downgrade(<prev>)`` en una DB EFIMERA DEDICADA, verificando que la tabla y el
  enum se crean y se borran limpio.
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
_MIGRATION = _BACKEND / "alembic" / "versions" / "20260614_1700_conversation_turns_table.py"

_TABLE = "conversation_turns"
_ENUM = "turn_role_enum"
# Head previo (audit_log block-update trigger): la nueva migracion encadena a este.
_PREV_REVISION = "a1f3c9d27e84"
_NEW_REVISION = "c4e8a1d50b93"


def test_migration_chains_to_previous_head() -> None:
    """Unit (sin DB): la revision encadena al head previo y trae upgrade/downgrade."""
    spec = importlib.util.spec_from_file_location("_conv_turns_migration", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == _NEW_REVISION
    assert module.down_revision == _PREV_REVISION
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_declares_table_and_enum() -> None:
    """Unit (sin DB): el upgrade crea la tabla ``conversation_turns`` y el enum."""
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


_ROUNDTRIP_DB = "ynara_conv_turns_roundtrip"


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
    """Integracion: upgrade(head) crea la tabla + enum; downgrade(prev) los borra.

    Corre en una DB EFIMERA DEDICADA (no la ``ynara_test`` compartida): se aplica
    ``upgrade head`` (la cadena entera, incl. esta migracion) y luego
    ``downgrade <prev>`` (revierte SOLO esta migracion), verificando el round-trip
    de la tabla operativa + su enum.
    """
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
        assert has_table, "conversation_turns no quedo creada tras upgrade head"
        assert has_enum, "turn_role_enum no quedo creado tras upgrade head"

        # downgrade SOLO esta migracion (al head previo): la tabla + enum se borran,
        # el resto del schema (tablas sagradas) sobrevive.
        command.downgrade(cfg, _PREV_REVISION)
        has_table_after, has_enum_after = asyncio.run(_table_and_enum_present(ephemeral_dsn))
        assert not has_table_after, "el downgrade no borro conversation_turns"
        assert not has_enum_after, "el downgrade no borro turn_role_enum"
    finally:
        asyncio.run(_drop_db(maintenance_dsn, _ROUNDTRIP_DB))
