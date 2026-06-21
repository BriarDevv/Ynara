"""Unit tests del DRIFT GUARD de catálogos (`scripts/check_doc_catalogs.py`).

Sin DB ni servicios: arma `alembic/versions`, `app/api/v1` y `docs/*.md` de
ejemplo en `tmp_path` y ejercita la lógica de parseo + comparación.

El script vive fuera del paquete `app`, así que se importa por path con
`importlib` (no hay `pythonpath` configurado para `scripts/`).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_doc_catalogs.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_doc_catalogs", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cdc = _load_module()


# --- fixtures de scaffolding ----------------------------------------------


def _make_backend(
    tmp_path: Path,
    *,
    revisions: dict[str, str],
    migrations_doc_revs: list[str],
    routes_py: str,
    endpoints_doc_text: str,
) -> Path:
    """Crea un backend_root mínimo en tmp_path con los archivos relevantes."""
    backend = tmp_path / "backend"
    versions = backend / "alembic" / "versions"
    api = backend / "app" / "api" / "v1"
    docs = backend / "docs"
    for directory in (versions, api, docs):
        directory.mkdir(parents=True, exist_ok=True)

    # migraciones: un archivo por revision con la línea estándar de Alembic.
    for rev, filename in revisions.items():
        (versions / filename).write_text(
            f'"""migración de ejemplo."""\n\nrevision: str = "{rev}"\n'
            "down_revision: str | None = None\n",
            encoding="utf-8",
        )
    (versions / "__init__.py").write_text("", encoding="utf-8")

    # doc de migraciones: una tabla mencionando solo las revisions pedidas.
    doc_lines = ["# MIGRATIONS.md", "", "## Migraciones registradas", ""]
    doc_lines += [f"| archivo | `{rev}` | ... |" for rev in migrations_doc_revs]
    (docs / "MIGRATIONS.md").write_text("\n".join(doc_lines) + "\n", encoding="utf-8")

    # api: un único módulo con los decoradores pasados.
    (api / "routes.py").write_text(routes_py, encoding="utf-8")

    # doc de endpoints.
    (docs / "ENDPOINTS.md").write_text(endpoints_doc_text, encoding="utf-8")

    return backend


# --- extract_revisions ----------------------------------------------------


def test_extract_revisions_parsea_la_linea_revision(tmp_path: Path) -> None:
    backend = _make_backend(
        tmp_path,
        revisions={"aaa111": "20260101_0000_a.py", "bbb222": "20260102_0000_b.py"},
        migrations_doc_revs=[],
        routes_py="",
        endpoints_doc_text="",
    )

    revisions = cdc.extract_revisions(backend / "alembic" / "versions")

    assert revisions == {
        "aaa111": "20260101_0000_a.py",
        "bbb222": "20260102_0000_b.py",
    }


def test_extract_revisions_ignora_init(tmp_path: Path) -> None:
    backend = _make_backend(
        tmp_path,
        revisions={"aaa111": "20260101_0000_a.py"},
        migrations_doc_revs=[],
        routes_py="",
        endpoints_doc_text="",
    )

    # __init__.py existe pero no tiene línea revision: no debe aparecer.
    revisions = cdc.extract_revisions(backend / "alembic" / "versions")

    assert list(revisions) == ["aaa111"]


# --- migraciones: drift estricto ------------------------------------------


def test_revision_faltante_se_reporta_como_drift(tmp_path: Path) -> None:
    backend = _make_backend(
        tmp_path,
        revisions={"aaa111": "20260101_0000_a.py", "bbb222": "20260102_0000_b.py"},
        migrations_doc_revs=["aaa111"],  # falta bbb222
        routes_py="",
        endpoints_doc_text="",
    )

    missing = cdc.find_missing_revisions(
        backend / "alembic" / "versions", backend / "docs" / "MIGRATIONS.md"
    )

    assert missing == [("bbb222", "20260102_0000_b.py")]


def test_run_devuelve_1_cuando_falta_una_revision(tmp_path: Path) -> None:
    backend = _make_backend(
        tmp_path,
        revisions={"aaa111": "20260101_0000_a.py", "bbb222": "20260102_0000_b.py"},
        migrations_doc_revs=["aaa111"],  # falta bbb222
        routes_py="",
        endpoints_doc_text="",
    )

    assert cdc.run(backend) == 1


def test_run_devuelve_0_cuando_todo_esta_registrado(tmp_path: Path) -> None:
    backend = _make_backend(
        tmp_path,
        revisions={"aaa111": "20260101_0000_a.py", "bbb222": "20260102_0000_b.py"},
        migrations_doc_revs=["aaa111", "bbb222"],  # todas presentes
        routes_py='@router.get("/foo")\ndef foo(): ...\n',
        endpoints_doc_text="GET `/foo` documentado.\n",
    )

    assert cdc.run(backend) == 0


# --- endpoints: warning informativo (no falla) ----------------------------


def test_extract_routes_parsea_metodos_y_paths(tmp_path: Path) -> None:
    routes_py = (
        '@router.get("/auth/me")\n'
        "def me(): ...\n\n"
        "@router.post('/chat')\n"
        "def chat(): ...\n\n"
        '@router.delete("/memory/{ref}")\n'
        "def wipe(): ...\n"
    )
    backend = _make_backend(
        tmp_path,
        revisions={},
        migrations_doc_revs=[],
        routes_py=routes_py,
        endpoints_doc_text="",
    )

    routes = cdc.extract_routes(backend / "app" / "api" / "v1")

    assert ("GET", "/auth/me", "routes.py") in routes
    assert ("POST", "/chat", "routes.py") in routes
    assert ("DELETE", "/memory/{ref}", "routes.py") in routes


def test_endpoint_no_documentado_se_reporta_pero_no_falla(tmp_path: Path) -> None:
    backend = _make_backend(
        tmp_path,
        revisions={"aaa111": "20260101_0000_a.py"},
        migrations_doc_revs=["aaa111"],  # migraciones OK
        routes_py='@router.get("/no-documentado")\ndef x(): ...\n',
        endpoints_doc_text="GET `/otro` documentado.\n",  # no menciona /no-documentado
    )

    unmentioned = cdc.find_unmentioned_routes(
        backend / "app" / "api" / "v1", backend / "docs" / "ENDPOINTS.md"
    )
    assert unmentioned == [("GET", "/no-documentado", "routes.py")]

    # CLAVE: endpoint sin documentar NO debe bloquear (run sigue en 0).
    assert cdc.run(backend) == 0


def test_endpoint_match_fuzzy_por_substring(tmp_path: Path) -> None:
    # El decorador usa /auth/register pero el doc lo menciona como /v1/auth/register:
    # el substring matchea, así que NO debe reportarse como faltante.
    backend = _make_backend(
        tmp_path,
        revisions={},
        migrations_doc_revs=[],
        routes_py='@router.post("/auth/register")\ndef r(): ...\n',
        endpoints_doc_text="POST `/v1/auth/register` — crea usuario.\n",
    )

    unmentioned = cdc.find_unmentioned_routes(
        backend / "app" / "api" / "v1", backend / "docs" / "ENDPOINTS.md"
    )

    assert unmentioned == []
