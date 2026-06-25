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


# --- helper para los checks nuevos ----------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --- modelos: drift estricto ----------------------------------------------


def test_extract_table_names_parsea_tablename(tmp_path: Path) -> None:
    models = tmp_path / "app" / "models"
    _write(models / "user.py", 'class User(Base):\n    __tablename__ = "users"\n')
    _write(models / "task.py", 'class Task(Base):\n    __tablename__ = "tasks"\n')
    _write(models / "__init__.py", "")  # sin __tablename__: ignorado

    tables = cdc.extract_table_names(models)

    assert tables == {"users": "user.py", "tasks": "task.py"}


def test_tabla_faltante_en_models_doc_es_drift(tmp_path: Path) -> None:
    models = tmp_path / "app" / "models"
    _write(models / "task.py", 'class Task(Base):\n    __tablename__ = "tasks"\n')
    doc = tmp_path / "docs" / "MODELS.md"
    _write(doc, "# MODELS\n\nSolo `users` documentado.\n")

    missing = cdc.find_missing_tables(models, doc)

    assert missing == [("tasks", "task.py")]


# --- tools: warning informativo -------------------------------------------


def test_extract_tool_names_fstring_y_literal(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    _write(
        tools / "calendar.py",
        '_NAMESPACE = "calendar"\n\nclass T:\n    name = f"{_NAMESPACE}.create_event"\n',
    )
    _write(tools / "reminder.py", 'class R:\n    name = "reminder.set"\n')

    names = cdc.extract_tool_names(tools)

    assert names == {"calendar.create_event", "reminder.set"}


def test_tool_no_documentada_se_reporta(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    _write(tools / "x.py", '_NAMESPACE = "x"\nname = f"{_NAMESPACE}.do"\n')
    doc = tmp_path / "TOOLS.md"
    _write(doc, "# TOOLS\nsin la tool.\n")

    assert cdc.find_unmentioned_tools(tools, doc) == ["x.do"]


# --- mapa de paquetes: drift estricto -------------------------------------


def test_extract_app_packages_solo_dirs_con_init(tmp_path: Path) -> None:
    app = tmp_path / "app"
    _write(app / "core" / "__init__.py", "")
    _write(app / "llm" / "__init__.py", "")
    _write(app / "__pycache__" / "x.py", "")  # dunder dir -> ignorado
    _write(app / "main.py", "")  # archivo top-level -> no es paquete
    (app / "sinpkg").mkdir()  # dir sin __init__.py -> ignorado

    assert cdc.extract_app_packages(app) == ["core", "llm"]


def test_paquete_no_mapeado_es_drift(tmp_path: Path) -> None:
    app = tmp_path / "app"
    _write(app / "calendar" / "__init__.py", "")
    _write(app / "core" / "__init__.py", "")
    agents = tmp_path / "AGENTS.md"
    _write(agents, "# AGENTS\n\n```\napp/\n+-- core/\n```\n")  # falta calendar/

    assert cdc.find_unmapped_packages(app, agents) == ["calendar"]


# --- conteos en prosa: drift estricto (DOC-R3) ----------------------------


def test_count_domain_enums_solo_app_enums(tmp_path: Path) -> None:
    # Tres StrEnum en el módulo: el conteo es 3 (otras clases no cuentan).
    enums = tmp_path / "app" / "enums.py"
    _write(
        enums,
        "from enum import StrEnum\n\n"
        "class Mode(StrEnum):\n    A = 'a'\n\n"
        "class Layer(StrEnum):\n    B = 'b'\n\n"
        "class Role(StrEnum):\n    C = 'c'\n\n"
        "class NoEnum:\n    pass\n",
    )

    assert cdc.count_domain_enums(enums) == 3


def test_count_domain_enums_modulo_ausente(tmp_path: Path) -> None:
    assert cdc.count_domain_enums(tmp_path / "app" / "enums.py") == 0


def test_extract_prose_counts_parsea_los_tres(tmp_path: Path) -> None:
    doc = tmp_path / "AGENTS.md"
    _write(doc, "Migraciones: cadena de **11**; total 10 tablas, 7 enums, pgvector.\n")

    counts = cdc.extract_prose_counts(doc)

    assert counts == {"migrations": 11, "tables": 10, "enums": 7}


def test_extract_prose_counts_clave_ausente_es_none(tmp_path: Path) -> None:
    doc = tmp_path / "README.md"
    _write(doc, "Solo menciona 10 tablas, nada más.\n")

    counts = cdc.extract_prose_counts(doc)

    assert counts == {"migrations": None, "tables": 10, "enums": None}


def test_prose_count_match_no_es_drift(tmp_path: Path) -> None:
    doc = tmp_path / "AGENTS.md"
    _write(doc, "cadena de **11**; total 10 tablas, 7 enums.\n")

    drift = cdc.find_prose_count_drift(doc, real_migrations=11, real_tables=10, real_enums=7)

    assert drift == []


def test_prose_count_mismatch_es_drift(tmp_path: Path) -> None:
    # La prosa dice 9 migraciones pero el código tiene 11: drift.
    doc = tmp_path / "README.md"
    _write(doc, "cadena de **9**; total 10 tablas, 7 enums.\n")

    drift = cdc.find_prose_count_drift(doc, real_migrations=11, real_tables=10, real_enums=7)

    assert drift == [("migrations", 9, 11)]


def test_prose_count_clave_ausente_se_ignora(tmp_path: Path) -> None:
    # El doc no declara enums: aunque el real sea 7, no se reporta drift por enums.
    doc = tmp_path / "README.md"
    _write(doc, "cadena de **11**; total 10 tablas.\n")

    drift = cdc.find_prose_count_drift(doc, real_migrations=11, real_tables=10, real_enums=7)

    assert drift == []


def _make_full_backend(
    tmp_path: Path,
    *,
    agents_prose: str,
    readme_prose: str,
) -> Path:
    """backend_root completo (migración + modelo + paquete + enums) para `run`.

    Los conteos reales quedan fijos en 1 migración / 1 tabla / 2 enums; los
    tests varían solo la prosa de AGENTS.md / README.md.
    """
    backend = tmp_path / "backend"
    _write(
        backend / "alembic" / "versions" / "0001_init.py",
        'revision: str = "aaa111"\n',
    )
    _write(backend / "docs" / "MIGRATIONS.md", "| init | `aaa111` |\n")
    _write(
        backend / "app" / "models" / "user.py",
        'class User(Base):\n    __tablename__ = "users"\n',
    )
    _write(backend / "docs" / "MODELS.md", "`users` documentado.\n")
    _write(backend / "app" / "core" / "__init__.py", "")
    _write(
        backend / "app" / "enums.py",
        "from enum import StrEnum\n\n"
        "class A(StrEnum):\n    X = 'x'\n\n"
        "class B(StrEnum):\n    Y = 'y'\n",
    )
    _write(
        backend / "AGENTS.md",
        f"# AGENTS\n\n```\napp/\n+-- core/\n```\n\n{agents_prose}\n",
    )
    _write(backend / "README.md", f"# README\n\n{readme_prose}\n")
    return backend


def test_run_falla_con_drift_de_conteos_en_prosa(tmp_path: Path) -> None:
    # Reales: 1 migración / 1 tabla / 2 enums. La prosa miente (9 migraciones).
    backend = _make_full_backend(
        tmp_path,
        agents_prose="cadena de **9**; 1 tablas, 2 enums.",
        readme_prose="cadena de **1**; 1 tablas, 2 enums.",
    )

    assert cdc.run(backend) == 1


def test_run_ok_con_conteos_en_prosa_correctos(tmp_path: Path) -> None:
    # Reales: 1 migración / 1 tabla / 2 enums. La prosa de ambos docs coincide.
    backend = _make_full_backend(
        tmp_path,
        agents_prose="cadena de **1**; total 1 tablas, 2 enums, pgvector.",
        readme_prose="cadena de **1**; 1 tablas, 2 enums.",
    )

    assert cdc.run(backend) == 0
