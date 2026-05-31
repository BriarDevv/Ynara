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
from urllib.parse import urlsplit, urlunsplit

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


# DB efimera dedicada del roundtrip: se crea y dropea por el test (ver abajo).
_ROUNDTRIP_DB = "ynara_migration_roundtrip"


def _swap_database(dsn: str, dbname: str) -> str:
    """Devuelve ``dsn`` con la base de datos del path reemplazada por ``dbname``."""
    return urlunsplit(urlsplit(dsn)._replace(path=f"/{dbname}"))


async def _create_db(maintenance_dsn: str, name: str) -> None:
    """Crea (recreando si quedo de una corrida fallida) la DB ``name``.

    CREATE/DROP DATABASE no corren dentro de una transaccion; asyncpg ejecuta en
    autocommit. ``WITH (FORCE)`` (PG13+) corta conexiones colgadas a la DB target.
    El nombre es una constante hardcodeada (``_ROUNDTRIP_DB``), no input externo.
    """
    conn = await asyncpg.connect(dsn=maintenance_dsn)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


async def _drop_db(maintenance_dsn: str, name: str) -> None:
    """Dropea la DB efimera ``name`` (idempotente)."""
    conn = await asyncpg.connect(dsn=maintenance_dsn)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    finally:
        await conn.close()


@pytest.mark.integration
def test_upgrade_downgrade_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Integracion: upgrade crea el schema y downgrade lo borra (incl. vector).

    Corre en una DB EFIMERA DEDICADA (la crea y la dropea este test), NO en la
    ``TEST_DATABASE_URL`` (``ynara_test``) compartida: el ``downgrade(base)``
    destruye el schema, y otros tests de integracion asumen que ``ynara_test`` lo
    tiene persistente (el conftest no lo recrea por test). Aislar el roundtrip en
    su propia DB elimina el flake de que su drop pise a otro test bajo cierto
    timing. ``env.py`` de alembic toma ``TEST_DATABASE_URL``, asi que se la apunta
    a la DB efimera SOLO durante este test (``monkeypatch`` la restaura al salir).
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
        tables, enums, vector = asyncio.run(_schema_snapshot(ephemeral_dsn))
        assert _TABLES <= tables, f"faltan tablas: {_TABLES - tables}"
        assert _ENUMS <= enums, f"faltan enums: {_ENUMS - enums}"
        assert vector == 1, "la extension vector no quedo instalada"

        command.downgrade(cfg, "base")
        tables_after, enums_after, vector_after = asyncio.run(_schema_snapshot(ephemeral_dsn))
        assert not (_TABLES & tables_after), "el downgrade no borro las tablas"
        assert not (_ENUMS & enums_after), "el downgrade no borro los enums"
        assert vector_after == 0, "el downgrade no borro la extension vector"
    finally:
        # Dropear la DB efimera pase lo que pase (la ynara_test compartida nunca
        # se toco): aunque un assert falle, no queda basura ni schema a medias.
        asyncio.run(_drop_db(maintenance_dsn, _ROUNDTRIP_DB))
