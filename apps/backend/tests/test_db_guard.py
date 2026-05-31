"""Tests unitarios del guard anti-prod (``app.core.db_guard``).

NO son ``integration``: no tocan DB ni red. Cubren dos cosas:

1. ``is_prod_db_host`` — helper puro de detección de host de prod (Supabase)
   vs. dev local. Tabla de casos parametrizada.
2. ``guard_against_prod_db_in_dev`` — la lógica del guard con sus 4 escapes.
   ``env`` y ``modules`` se inyectan (no se monkeypatchea ``os.environ`` /
   ``sys.modules``) para poder forzar de forma determinista tanto la rama
   "bajo pytest" como la rama "NO pytest" — clave porque el propio test SÍ
   corre bajo pytest.
"""

from __future__ import annotations

import pytest

from app.core.db_guard import (
    ALLOW_PROD_DB_ENV,
    guard_against_prod_db_in_dev,
    is_prod_db_host,
)

# Connection string de prod tipo el del incidente (pooler de Supabase). Sin
# credenciales reales: usuario/password placeholder, nunca un secreto.
_PROD_URL = "postgresql://postgres:[pw]@db.abcdefgh.pooler.supabase.com:5432/postgres"
_PROD_URL_DIRECT = "postgresql://postgres:[pw]@db.abcdefgh.supabase.co:5432/postgres"
_DEV_URL = "postgresql://postgres:test@localhost:5433/ynara_dev"


# ---------------------------------------------------------------------------
# is_prod_db_host — helper puro
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # --- hosts de PROD (Supabase) ---
        ("postgresql://u:p@db.ref.supabase.co:5432/postgres", True),
        ("postgresql://u:p@aws-0-us-east-1.pooler.supabase.com:6543/postgres", True),
        ("postgresql://u:p@aws-0-eu-west-2.pooler.supabase.com:5432/postgres", True),
        ("postgresql://u:p@something.supabase.com:5432/postgres", True),
        # asyncpg scheme: debe parsear igual
        ("postgresql+asyncpg://u:p@db.ref.supabase.co:5432/postgres", True),
        # case-insensitive (host normalizado a minúsculas)
        ("postgresql://u:p@DB.REF.SUPABASE.CO:5432/postgres", True),
        # --- hosts de DEV / local → NO prod ---
        ("postgresql://postgres:test@localhost:5433/ynara_dev", False),
        ("postgresql://postgres:test@127.0.0.1:5433/ynara_test", False),
        ("postgresql+asyncpg://postgres:test@localhost:5432/ynara_dev", False),
        ("postgresql://postgres:test@db:5432/ynara", False),  # host de docker-compose
        # un dominio que solo *contiene* "supabase" pero no matchea los sufijos
        ("postgresql://u:p@supabase.evil.example.com:5432/db", False),
        # placeholders con corchetes (formato del .env.example): harían reventar
        # a urlsplit().hostname con ValueError; el helper debe seguir detectando.
        ("postgresql://postgres:[password]@db.ref.supabase.co:5432/postgres", True),
        ("postgresql://postgres:[password]@aws-0.pooler.supabase.com:6543/postgres", True),
        ("postgresql://postgres:[password]@localhost:5433/ynara_dev", False),
        # basura / vacío → False (no rompe)
        ("", False),
        ("not-a-url", False),
    ],
)
def test_is_prod_db_host(url: str, expected: bool) -> None:
    assert is_prod_db_host(url) is expected


# ---------------------------------------------------------------------------
# guard_against_prod_db_in_dev — escapes y disparo
# ---------------------------------------------------------------------------
# Para aislar la rama "bajo pytest" usamos env/modules vacíos. Para probar la
# rama "NO pytest" + disparo real, pasamos env/modules SIN señales de pytest.

_NO_PYTEST_ENV: dict[str, str] = {}
_NO_PYTEST_MODULES: dict[str, object] = {}


def test_production_does_not_raise_even_with_prod_host() -> None:
    """environment=production → no levanta aunque el host sea de prod."""
    # Sin escapes de pytest: si no fuera por environment=production, dispararía.
    guard_against_prod_db_in_dev(
        environment="production",
        database_url=_PROD_URL,
        env=_NO_PYTEST_ENV,
        modules=_NO_PYTEST_MODULES,
    )


@pytest.mark.parametrize("flag", ["1", "true", "yes", "TRUE", "Yes", " 1 "])
def test_explicit_opt_in_does_not_raise(flag: str) -> None:
    """YNARA_ALLOW_PROD_DB truthy → no levanta (dev-contra-prod a propósito)."""
    guard_against_prod_db_in_dev(
        environment="development",
        database_url=_PROD_URL,
        env={ALLOW_PROD_DB_ENV: flag},
        modules=_NO_PYTEST_MODULES,
    )


@pytest.mark.parametrize("flag", ["0", "false", "no", "", "maybe"])
def test_non_truthy_opt_in_does_not_escape(flag: str) -> None:
    """Un valor NO-truthy de la flag no cuenta como opt-in → sí dispara."""
    with pytest.raises(RuntimeError):
        guard_against_prod_db_in_dev(
            environment="development",
            database_url=_PROD_URL,
            env={ALLOW_PROD_DB_ENV: flag},
            modules=_NO_PYTEST_MODULES,
        )


def test_under_pytest_via_env_var_does_not_raise() -> None:
    """PYTEST_CURRENT_TEST presente → no levanta (rama pytest por env)."""
    guard_against_prod_db_in_dev(
        environment="development",
        database_url=_PROD_URL,
        env={"PYTEST_CURRENT_TEST": "tests/x.py::test_y (call)"},
        modules=_NO_PYTEST_MODULES,
    )


def test_under_pytest_via_sys_modules_does_not_raise() -> None:
    """``pytest`` en sys.modules → no levanta (rama pytest por módulo)."""
    import pytest as _pytest_mod

    guard_against_prod_db_in_dev(
        environment="development",
        database_url=_PROD_URL,
        env=_NO_PYTEST_ENV,
        modules={"pytest": _pytest_mod},
    )


def test_defaults_use_real_pytest_env_so_no_raise() -> None:
    """Sin inyectar env/modules: el guard usa os.environ/sys.modules reales.

    Como ESTE test corre bajo pytest, la rama pytest aplica y NO levanta aunque
    el host sea de prod. Verifica que los defaults (os.environ / sys.modules)
    se cablean bien.
    """
    guard_against_prod_db_in_dev(
        environment="development",
        database_url=_PROD_URL,
    )


@pytest.mark.parametrize("prod_url", [_PROD_URL, _PROD_URL_DIRECT])
def test_dev_against_prod_host_without_escapes_raises(prod_url: str) -> None:
    """dev + host prod + sin opt-in + sin pytest → RuntimeError (rama no-pytest)."""
    with pytest.raises(RuntimeError) as exc_info:
        guard_against_prod_db_in_dev(
            environment="development",
            database_url=prod_url,
            env=_NO_PYTEST_ENV,
            modules=_NO_PYTEST_MODULES,
        )
    msg = str(exc_info.value)
    # El mensaje es accionable y NO filtra credenciales del DSN de PROD.
    assert ALLOW_PROD_DB_ENV in msg
    assert "PRODUCCIÓN" in msg or "producción" in msg
    assert "[pw]" not in msg  # nunca la password de prod
    assert "postgres:[pw]@" not in msg  # nunca la netloc con credenciales de prod
    # El host de prod SÍ aparece (es lo accionable y no es secreto); el DSN de
    # prod COMPLETO no. (El mensaje incluye un DSN de ejemplo de dev local, que
    # es público por diseño — por eso afirmamos sobre el de prod puntualmente.)
    assert prod_url not in msg


def test_dev_against_local_host_does_not_raise() -> None:
    """dev + host localhost → no levanta (es la DB de dev local)."""
    guard_against_prod_db_in_dev(
        environment="development",
        database_url=_DEV_URL,
        env=_NO_PYTEST_ENV,
        modules=_NO_PYTEST_MODULES,
    )


def test_staging_against_prod_host_raises() -> None:
    """Sólo 'production' es escape de environment; staging dispara igual."""
    with pytest.raises(RuntimeError):
        guard_against_prod_db_in_dev(
            environment="staging",
            database_url=_PROD_URL,
            env=_NO_PYTEST_ENV,
            modules=_NO_PYTEST_MODULES,
        )
