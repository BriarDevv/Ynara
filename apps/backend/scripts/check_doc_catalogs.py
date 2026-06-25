#!/usr/bin/env python3
"""DRIFT GUARD de los catálogos de docs del backend.

Evita que `docs/MIGRATIONS.md` y `docs/ENDPOINTS.md` queden stale respecto
del código (el bug que ya nos pasó: agregar una migración / endpoint y
olvidar registrarlo en el catálogo).

Valida SEIS cosas contra el estado actual del repo:

a) MIGRACIONES (ESTRICTO, falla el build):
   cada revision declarada en `alembic/versions/*.py`
   (línea `revision: str = "..."`) debe estar listada en `docs/MIGRATIONS.md`.

b) MODELS (ESTRICTO, falla el build):
   cada `__tablename__` de `app/models/*.py` debe aparecer en `docs/MODELS.md`.

c) MAPA DE PAQUETES (ESTRICTO, falla el build):
   cada paquete top-level de `app/` (directorio con `__init__.py`) debe aparecer
   en el mapa de código de `AGENTS.md`. Convierte el drift del mapa (la causa de
   que se "perdieran" calendar/ y tasks/) en una falla detectable.

c-bis) CONTEOS EN PROSA (ESTRICTO, falla el build) — DOC-R3:
   los conteos en prosa de `AGENTS.md` y `README.md` (X migraciones, Y tablas,
   Z enums) deben coincidir con los conteos REALES del código (len de revisiones
   de Alembic, len de `__tablename__` de models, número de `StrEnum` en
   `app/enums.py`). Cierra la causa-raíz del drift de prosa: antes los números
   "cadena de N", "M tablas", "K enums" se editaban a mano y quedaban stale.

d) ENDPOINTS (INFORMATIVO, NO falla el build):
   cada path declarado en `app/api/v1/**/*.py` (decoradores
   `@router.get/post/patch/delete/put("...")`) debería aparecer mencionado en
   `docs/ENDPOINTS.md`. Parseo fuzzy (prefijo `/v1`, varias formas del path) ->
   warning para no generar falsos positivos bloqueantes.

e) TOOLS (INFORMATIVO, NO falla el build):
   cada `name` de tool de `app/llm/tools/*.py` (literal o f-string con
   `_NAMESPACE`) debería aparecer en `docs/TOOLS.md`. Parseo fuzzy -> warning.

Solo stdlib. Pensado para correr en CI con:

    cd apps/backend && uv run python scripts/check_doc_catalogs.py

Refactorizado en funciones testeables + guard `if __name__ == "__main__"`
(ver `tests/scripts/test_check_doc_catalogs.py`).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# --- regexes de parseo ----------------------------------------------------

# Línea: revision: str = "b7b06025f4bb"  (comillas simples o dobles)
_REVISION_RE = re.compile(
    r"""^\s*revision\s*:\s*str\s*=\s*['"](?P<rev>[^'"]+)['"]""",
    re.MULTILINE,
)

# Decorador de ruta: @router.get("/auth/me", ...) / @app.post('/chat')
# Captura método + primer string-literal (el path).
_ROUTE_RE = re.compile(
    r"""@\w+\.(?P<method>get|post|patch|delete|put)\s*\(\s*['"](?P<path>[^'"]+)['"]""",
    re.IGNORECASE,
)


# --- migraciones (estricto) -----------------------------------------------


def extract_revisions(versions_dir: Path) -> dict[str, str]:
    """Devuelve {revision: nombre_de_archivo} para cada migración Alembic.

    Parsea la línea `revision: str = "..."` de cada `*.py` en versions_dir
    (ignora `__init__.py` y archivos sin esa línea, p. ej. helpers).
    """
    revisions: dict[str, str] = {}
    for path in sorted(versions_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        match = _REVISION_RE.search(text)
        if match:
            revisions[match.group("rev")] = path.name
    return revisions


def find_missing_revisions(versions_dir: Path, migrations_doc: Path) -> list[tuple[str, str]]:
    """Revisions presentes en el código pero NO mencionadas en MIGRATIONS.md.

    Devuelve una lista de tuplas (revision, archivo) ordenada por archivo.
    """
    revisions = extract_revisions(versions_dir)
    doc_text = migrations_doc.read_text(encoding="utf-8") if migrations_doc.exists() else ""
    missing = [(rev, filename) for rev, filename in revisions.items() if rev not in doc_text]
    return sorted(missing, key=lambda item: item[1])


# --- endpoints (informativo) ----------------------------------------------


def extract_routes(api_dir: Path) -> list[tuple[str, str, str]]:
    """Devuelve [(method, path, archivo)] para cada decorador de ruta.

    Recorre recursivamente `api_dir` buscando `@<x>.<verbo>("<path>")`.
    """
    routes: list[tuple[str, str, str]] = []
    for path in sorted(api_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for match in _ROUTE_RE.finditer(text):
            method = match.group("method").upper()
            route_path = match.group("path")
            routes.append((method, route_path, path.name))
    return routes


def find_unmentioned_routes(api_dir: Path, endpoints_doc: Path) -> list[tuple[str, str, str]]:
    """Rutas declaradas en el código pero NO mencionadas en ENDPOINTS.md.

    Match fuzzy: busca el path del decorador como substring del doc. Como los
    routers montan con prefijo `/v1`, la doc puede usar `/v1/auth/register` y
    el decorador `/auth/register`; el substring matchea igual.
    """
    routes = extract_routes(api_dir)
    doc_text = endpoints_doc.read_text(encoding="utf-8") if endpoints_doc.exists() else ""
    unmentioned = [
        (method, route_path, filename)
        for method, route_path, filename in routes
        if route_path not in doc_text
    ]
    return unmentioned


# --- modelos (estricto) ---------------------------------------------------

# Línea: __tablename__ = "tasks"
_TABLENAME_RE = re.compile(
    r"""^\s*__tablename__\s*=\s*['"](?P<table>[a-z_]+)['"]""",
    re.MULTILINE,
)


def extract_table_names(models_dir: Path) -> dict[str, str]:
    """Devuelve {tabla: archivo} para cada modelo con ``__tablename__``."""
    tables: dict[str, str] = {}
    for path in sorted(models_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        for match in _TABLENAME_RE.finditer(path.read_text(encoding="utf-8")):
            tables[match.group("table")] = path.name
    return tables


def find_missing_tables(models_dir: Path, models_doc: Path) -> list[tuple[str, str]]:
    """Tablas declaradas en el código pero NO mencionadas en MODELS.md."""
    tables = extract_table_names(models_dir)
    doc_text = models_doc.read_text(encoding="utf-8") if models_doc.exists() else ""
    missing = [(table, filename) for table, filename in tables.items() if table not in doc_text]
    return sorted(missing, key=lambda item: item[0])


# --- tools (informativo) --------------------------------------------------

# _NAMESPACE = "calendar"  (al tope del módulo de tools)
_NAMESPACE_RE = re.compile(r"""^\s*_NAMESPACE\s*=\s*['"](?P<ns>[a-z_]+)['"]""", re.MULTILINE)
# name = f"{_NAMESPACE}.create_event"  (f-string con el namespace del módulo)
_TOOL_FSTRING_RE = re.compile(r"""name\s*=\s*f['"]\{_NAMESPACE\}\.(?P<action>[a-z_]+)['"]""")
# name = "reminder.set"  (literal namespace.action)
_TOOL_LITERAL_RE = re.compile(r"""name\s*=\s*['"](?P<full>[a-z_]+\.[a-z_]+)['"]""")


def extract_tool_names(tools_dir: Path) -> set[str]:
    """Set de nombres de tool (``namespace.action``) declarados en el código.

    Maneja las dos formas de declarar ``name``: f-string con el ``_NAMESPACE``
    del módulo (``f"{_NAMESPACE}.create_event"``) y literal (``"reminder.set"``).
    Los stubs y las tools reales comparten ``name`` (dedup por set).
    """
    names: set[str] = set()
    for path in sorted(tools_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        ns_match = _NAMESPACE_RE.search(text)
        ns = ns_match.group("ns") if ns_match else None
        if ns:
            for match in _TOOL_FSTRING_RE.finditer(text):
                names.add(f"{ns}.{match.group('action')}")
        for match in _TOOL_LITERAL_RE.finditer(text):
            names.add(match.group("full"))
    return names


def find_unmentioned_tools(tools_dir: Path, tools_doc: Path) -> list[str]:
    """Nombres de tool declarados en el código pero NO mencionados en TOOLS.md."""
    names = extract_tool_names(tools_dir)
    doc_text = tools_doc.read_text(encoding="utf-8") if tools_doc.exists() else ""
    return sorted(name for name in names if name not in doc_text)


# --- mapa de paquetes (estricto) ------------------------------------------


def extract_app_packages(app_dir: Path) -> list[str]:
    """Paquetes top-level de ``app/`` (directorios con ``__init__.py``, sin dunder)."""
    packages: list[str] = []
    for path in sorted(app_dir.iterdir()):
        if not path.is_dir() or path.name.startswith((".", "__")):
            continue
        if (path / "__init__.py").exists():
            packages.append(path.name)
    return packages


def find_unmapped_packages(app_dir: Path, agents_doc: Path) -> list[str]:
    """Paquetes de ``app/`` ausentes del mapa de código de AGENTS.md.

    Convierte el drift del mapa (la causa de que se "perdieran" calendar/ y
    tasks/) en una falla detectable: cada paquete debe aparecer como ``pkg/`` o
    ``` `pkg` ``` en el texto de AGENTS.md.
    """
    packages = extract_app_packages(app_dir)
    doc_text = agents_doc.read_text(encoding="utf-8") if agents_doc.exists() else ""
    return [pkg for pkg in packages if f"{pkg}/" not in doc_text and f"`{pkg}`" not in doc_text]


# --- conteos en prosa (estricto, DOC-R3) ----------------------------------

# StrEnum cross-domain: `class Mode(StrEnum):` en app/enums.py (los que se
# materializan como tipos PG nativos). NO contamos StrEnums de otros módulos
# (p. ej. CircuitState en llm/clients/circuit.py): la prosa habla de los enums
# de DB, que viven todos en app/enums.py.
_STRENUM_RE = re.compile(r"""^class\s+\w+\(StrEnum\)\s*:""", re.MULTILINE)

# Conteos en prosa de AGENTS.md / README.md:
#   "cadena de **11**" / "cadena de 11"  -> migraciones
#   "10 tablas"                          -> tablas
#   "7 enums"                            -> enums
_PROSE_MIGRATIONS_RE = re.compile(r"cadena de \*{0,2}(?P<n>\d+)")
_PROSE_TABLES_RE = re.compile(r"\*{0,2}(?P<n>\d+)\*{0,2}\s+tablas\b")
_PROSE_ENUMS_RE = re.compile(r"\*{0,2}(?P<n>\d+)\*{0,2}\s+enums\b")


def count_domain_enums(enums_module: Path) -> int:
    """Número de ``StrEnum`` declarados en ``app/enums.py`` (enums de DB)."""
    if not enums_module.exists():
        return 0
    return len(_STRENUM_RE.findall(enums_module.read_text(encoding="utf-8")))


def extract_prose_counts(doc: Path) -> dict[str, int | None]:
    """Extrae los conteos en prosa (migraciones/tablas/enums) de un doc.

    Devuelve un dict con las claves ``migrations``/``tables``/``enums``; cada
    valor es el primer entero matcheado o ``None`` si el doc no declara ese
    conteo (no es drift que falte una clave: solo se comparan las presentes).
    """
    text = doc.read_text(encoding="utf-8") if doc.exists() else ""
    return {
        "migrations": _first_int(_PROSE_MIGRATIONS_RE, text),
        "tables": _first_int(_PROSE_TABLES_RE, text),
        "enums": _first_int(_PROSE_ENUMS_RE, text),
    }


def _first_int(pattern: re.Pattern[str], text: str) -> int | None:
    """Primer entero capturado por ``pattern`` en ``text``, o ``None``."""
    match = pattern.search(text)
    return int(match.group("n")) if match else None


def find_prose_count_drift(
    doc: Path,
    *,
    real_migrations: int,
    real_tables: int,
    real_enums: int,
) -> list[tuple[str, int, int]]:
    """Conteos en prosa de ``doc`` que NO coinciden con los reales del código.

    Devuelve una lista de tuplas ``(categoria, declarado_en_prosa, real)`` por
    cada mismatch. Una clave ausente en la prosa NO es drift (se ignora): solo
    se comparan los conteos que el doc efectivamente declara.
    """
    prose = extract_prose_counts(doc)
    reals = {"migrations": real_migrations, "tables": real_tables, "enums": real_enums}
    drift: list[tuple[str, int, int]] = []
    for category, real in reals.items():
        declared = prose[category]
        if declared is not None and declared != real:
            drift.append((category, declared, real))
    return drift


# --- runner ---------------------------------------------------------------


def run(backend_root: Path) -> int:
    """Corre los checks. Devuelve exit code (0 ok, 1 si hay drift estricto).

    Estricto (falla el build): MIGRACIONES, MODELS, PAQUETES del mapa,
    CONTEOS en prosa (DOC-R3).
    Informativo (warning): ENDPOINTS, TOOLS (parseo fuzzy).
    """
    versions_dir = backend_root / "alembic" / "versions"
    migrations_doc = backend_root / "docs" / "MIGRATIONS.md"
    api_dir = backend_root / "app" / "api" / "v1"
    endpoints_doc = backend_root / "docs" / "ENDPOINTS.md"
    models_dir = backend_root / "app" / "models"
    models_doc = backend_root / "docs" / "MODELS.md"
    tools_dir = backend_root / "app" / "llm" / "tools"
    tools_doc = backend_root / "docs" / "TOOLS.md"
    app_dir = backend_root / "app"
    agents_doc = backend_root / "AGENTS.md"
    readme_doc = backend_root / "README.md"
    enums_module = backend_root / "app" / "enums.py"

    print("== DRIFT GUARD: catálogos de docs ==")

    # a) MIGRACIONES (estricto)
    total_revisions = len(extract_revisions(versions_dir))
    missing_revisions = find_missing_revisions(versions_dir, migrations_doc)
    if missing_revisions:
        print(
            f"\n[MIGRACIONES] FALLA: {len(missing_revisions)} de {total_revisions} "
            f"revision(es) NO están en docs/MIGRATIONS.md:"
        )
        for rev, filename in missing_revisions:
            print(f"  - {rev}  ({filename})")
        print("\n  -> Registralas en la tabla 'Migraciones registradas' de docs/MIGRATIONS.md.")
    else:
        print(
            f"\n[MIGRACIONES] OK: {total_revisions} revision(es) registradas en docs/MIGRATIONS.md."
        )

    # b) MODELS (estricto)
    total_tables = len(extract_table_names(models_dir))
    missing_tables = find_missing_tables(models_dir, models_doc)
    if missing_tables:
        print(
            f"\n[MODELS] FALLA: {len(missing_tables)} de {total_tables} "
            f"tabla(s) NO están en docs/MODELS.md:"
        )
        for table, filename in missing_tables:
            print(f"  - {table}  ({filename})")
        print("\n  -> Registralas en el catálogo de docs/MODELS.md.")
    else:
        print(f"\n[MODELS] OK: {total_tables} tabla(s) registradas en docs/MODELS.md.")

    # c) PAQUETES del mapa (estricto)
    total_packages = len(extract_app_packages(app_dir))
    unmapped_packages = find_unmapped_packages(app_dir, agents_doc)
    if unmapped_packages:
        print(
            f"\n[MAPA] FALLA: {len(unmapped_packages)} de {total_packages} "
            f"paquete(s) de app/ NO aparecen en el mapa de AGENTS.md:"
        )
        for pkg in unmapped_packages:
            print(f"  - app/{pkg}/")
        print("\n  -> Agregalos al mapa de código (AGENTS.md §2).")
    else:
        print(f"\n[MAPA] OK: {total_packages} paquete(s) de app/ en el mapa de AGENTS.md.")

    # c-bis) CONTEOS EN PROSA (estricto, DOC-R3)
    real_migrations = total_revisions
    real_tables = total_tables
    real_enums = count_domain_enums(enums_module)
    prose_drift: list[tuple[str, str, int, int]] = []
    for doc in (agents_doc, readme_doc):
        for category, declared, real in find_prose_count_drift(
            doc,
            real_migrations=real_migrations,
            real_tables=real_tables,
            real_enums=real_enums,
        ):
            prose_drift.append((doc.name, category, declared, real))
    if prose_drift:
        print(
            f"\n[CONTEOS] FALLA: {len(prose_drift)} conteo(s) en prosa NO coinciden con "
            f"el código (reales: {real_migrations} migraciones / {real_tables} tablas / "
            f"{real_enums} enums):"
        )
        for doc_name, category, declared, real in prose_drift:
            print(f"  - {doc_name}: {category} dice {declared}, el código tiene {real}")
        print("\n  -> Corregí el conteo en prosa de AGENTS.md / README.md.")
    else:
        print(
            f"\n[CONTEOS] OK: prosa de AGENTS.md/README.md coincide con el código "
            f"({real_migrations} migraciones / {real_tables} tablas / {real_enums} enums)."
        )

    # d) ENDPOINTS (informativo)
    total_routes = len(extract_routes(api_dir))
    unmentioned_routes = find_unmentioned_routes(api_dir, endpoints_doc)
    if unmentioned_routes:
        print(
            f"\n[ENDPOINTS] WARNING (no bloquea): {len(unmentioned_routes)} de "
            f"{total_routes} ruta(s) NO aparecen en docs/ENDPOINTS.md:"
        )
        for method, route_path, filename in unmentioned_routes:
            print(f"  - {method} {route_path}  ({filename})")
        print(
            "\n  -> Considerá documentarlas en docs/ENDPOINTS.md "
            "(chequeo fuzzy, puede tener falsos positivos)."
        )
    else:
        print(f"\n[ENDPOINTS] OK: {total_routes} ruta(s) mencionadas en docs/ENDPOINTS.md.")

    # e) TOOLS (informativo)
    total_tools = len(extract_tool_names(tools_dir))
    unmentioned_tools = find_unmentioned_tools(tools_dir, tools_doc)
    if unmentioned_tools:
        print(
            f"\n[TOOLS] WARNING (no bloquea): {len(unmentioned_tools)} de "
            f"{total_tools} tool(s) NO aparecen en docs/TOOLS.md:"
        )
        for name in unmentioned_tools:
            print(f"  - {name}")
        print("\n  -> Considerá documentarlas en docs/TOOLS.md (parseo fuzzy de name).")
    else:
        print(f"\n[TOOLS] OK: {total_tools} tool(s) mencionadas en docs/TOOLS.md.")

    strict_drift = bool(missing_revisions or missing_tables or unmapped_packages or prose_drift)
    exit_code = 1 if strict_drift else 0
    print(f"\n== Resultado: {'FALLA (drift de catálogos)' if exit_code else 'OK'} ==")
    return exit_code


def main() -> int:
    # El script vive en apps/backend/scripts/, el backend_root es su parent.
    backend_root = Path(__file__).resolve().parent.parent
    return run(backend_root)


if __name__ == "__main__":
    sys.exit(main())
