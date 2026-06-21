#!/usr/bin/env python3
"""DRIFT GUARD de los catálogos de docs del backend.

Evita que `docs/MIGRATIONS.md` y `docs/ENDPOINTS.md` queden stale respecto
del código (el bug que ya nos pasó: agregar una migración / endpoint y
olvidar registrarlo en el catálogo).

Valida DOS cosas contra el estado actual del repo:

a) MIGRACIONES (ESTRICTO, falla el build):
   cada revision declarada en `alembic/versions/*.py`
   (línea `revision: str = "..."`) debe estar listada en `docs/MIGRATIONS.md`.
   Si falta alguna -> imprime cuáles y devuelve exit 1.

b) ENDPOINTS (INFORMATIVO, NO falla el build):
   cada path declarado en `app/api/v1/**/*.py` (decoradores
   `@router.get/post/patch/delete/put("...")`) debería aparecer mencionado en
   `docs/ENDPOINTS.md`. Si falta -> imprime un WARNING pero NO cambia el exit
   code. El parseo de rutas es fuzzy (los routers montan con prefijo `/v1` y la
   doc usa varias formas del mismo path); arrancamos como warning para no
   generar falsos positivos bloqueantes.

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


# --- runner ---------------------------------------------------------------


def run(backend_root: Path) -> int:
    """Corre ambos checks. Devuelve exit code (0 ok, 1 drift de migraciones)."""
    versions_dir = backend_root / "alembic" / "versions"
    migrations_doc = backend_root / "docs" / "MIGRATIONS.md"
    api_dir = backend_root / "app" / "api" / "v1"
    endpoints_doc = backend_root / "docs" / "ENDPOINTS.md"

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

    # b) ENDPOINTS (informativo)
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

    exit_code = 1 if missing_revisions else 0
    print(f"\n== Resultado: {'FALLA (drift de migraciones)' if exit_code else 'OK'} ==")
    return exit_code


def main() -> int:
    # El script vive en apps/backend/scripts/, el backend_root es su parent.
    backend_root = Path(__file__).resolve().parent.parent
    return run(backend_root)


if __name__ == "__main__":
    sys.exit(main())
