"""Tests de la migracion ``drop_redundant_conversation_turns_indexes`` (auditoria).

Tabla OPERATIVA (no sagrada). Valida que:

- **Unit (sin DB)**: la revision encadena al head previo y su ``upgrade`` dropea los
  dos indices redundantes (parseo del source con ``ast``).
- **Integracion** (``integration``): round-trip ``upgrade(head)`` / ``downgrade(prev)``
  en una DB EFIMERA DEDICADA, verificando que los indices redundantes desaparecen tras
  el upgrade (y el ``user_id`` + el UNIQUE sobreviven) y vuelven tras el downgrade.
- **Integracion full round-trip**: ``upgrade head`` -> ``downgrade base`` -> ``upgrade head``
  de TODA la cadena, validando que las migraciones revierten limpio (incl. la simetria
  de ``pgcrypto``: se instala en upgrade y se dropea en downgrade base).
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
_MIGRATION = (
    _BACKEND / "alembic" / "versions" / "20260615_0200_drop_redundant_conversation_turns_indexes.py"
)

_NEW_REVISION = "b7e2f4a16c9d"
_PREV_REVISION = "c4e8a1d50b93"  # conversation_turns (head previo)
_TABLE = "conversation_turns"
_REDUNDANT = ("ix_conversation_turns_session_id_seq", "ix_conversation_turns_session_id")
_KEPT = ("ix_conversation_turns_user_id", "uq_conversation_turns_session_id_seq")


# ---------------------------------------------------------------------------
# Unit (sin DB)
# ---------------------------------------------------------------------------


def test_migration_chains_to_previous_head() -> None:
    """La revision encadena a conversation_turns y trae upgrade/downgrade."""
    spec = importlib.util.spec_from_file_location("_drop_redundant_idx", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == _NEW_REVISION
    assert module.down_revision == _PREV_REVISION
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_upgrade_drops_the_redundant_indexes() -> None:
    """El ``upgrade`` dropea exactamente los dos indices redundantes."""
    tree = ast.parse(_MIGRATION.read_text(encoding="utf-8"))
    dropped: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "drop_index" and node.args:
            arg = node.args[0]
            # Nombre directo (Constant) o envuelto en op.f(...) (Call).
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                dropped.add(arg.value)
            elif isinstance(arg, ast.Call) and arg.args and isinstance(arg.args[0], ast.Constant):
                dropped.add(arg.args[0].value)
    assert set(_REDUNDANT) <= dropped


# ---------------------------------------------------------------------------
# Integracion (DB efimera dedicada)
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


async def _index_names(dsn: str) -> set[str]:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        rows = await conn.fetch(
            "select indexname from pg_indexes where schemaname = 'public' and tablename = $1",
            _TABLE,
        )
        return {r["indexname"] for r in rows}
    finally:
        await conn.close()


async def _pgcrypto_present(dsn: str) -> bool:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        return bool(
            await conn.fetchval("select count(*) from pg_extension where extname = 'pgcrypto'")
        )
    finally:
        await conn.close()


_ROUNDTRIP_DB = "ynara_drop_redundant_idx_roundtrip"


@pytest.mark.integration
def test_upgrade_downgrade_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """upgrade(head) saca los redundantes (deja user_id + UNIQUE); downgrade(prev) los repone."""
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
        after_up = asyncio.run(_index_names(ephemeral_dsn))
        for name in _REDUNDANT:
            assert name not in after_up, f"{name} deberia estar dropeado tras upgrade head"
        for name in _KEPT:
            assert name in after_up, f"{name} NO deberia haberse tocado"

        command.downgrade(cfg, _PREV_REVISION)
        after_down = asyncio.run(_index_names(ephemeral_dsn))
        for name in _REDUNDANT:
            assert name in after_down, f"el downgrade no repuso {name}"
    finally:
        asyncio.run(_drop_db(maintenance_dsn, _ROUNDTRIP_DB))


_FULL_DB = "ynara_full_roundtrip"


@pytest.mark.integration
def test_full_chain_roundtrip_is_reversible(monkeypatch: pytest.MonkeyPatch) -> None:
    """upgrade head -> downgrade base -> upgrade head: toda la cadena revierte limpio.

    Valida la simetria de extensiones (pgcrypto se instala en upgrade y se dropea en
    downgrade base) y que re-aplicar la cadena entera no falla (regla #3: migraciones
    sagradas reversibles).
    """
    base_dsn = _test_db_dsn()
    if not base_dsn:
        pytest.skip("TEST_DATABASE_URL no seteada (DB de tests dedicada, NO prod)")

    maintenance_dsn = _swap_database(base_dsn, "postgres")
    ephemeral_dsn = _swap_database(base_dsn, _FULL_DB)

    asyncio.run(_create_db(maintenance_dsn, _FULL_DB))
    monkeypatch.setenv("TEST_DATABASE_URL", ephemeral_dsn)
    cfg = _alembic_cfg()
    try:
        command.upgrade(cfg, "head")
        assert asyncio.run(_pgcrypto_present(ephemeral_dsn)), "pgcrypto deberia estar tras upgrade"

        command.downgrade(cfg, "base")
        assert not asyncio.run(_pgcrypto_present(ephemeral_dsn)), (
            "pgcrypto deberia dropearse en downgrade base (simetria del round-trip)"
        )
        # base = sin tablas de la app.
        assert asyncio.run(_index_names(ephemeral_dsn)) == set()

        # Re-aplicar toda la cadena no debe fallar.
        command.upgrade(cfg, "head")
        assert asyncio.run(_pgcrypto_present(ephemeral_dsn))
    finally:
        asyncio.run(_drop_db(maintenance_dsn, _FULL_DB))
