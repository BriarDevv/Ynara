"""Tests del schema de usuario, foco en ``time_zone`` (validación IANA).

Sin DB: puramente schema-level. Cubren:
- ``UserBase``/``UserOut`` default ``time_zone == "UTC"`` cuando no se setea.
- ``UserUpdate.time_zone`` válido (IANA real) pasa; inválido levanta ``ValidationError``
  (que FastAPI traduce a 422) SIN ecoar el valor inválido (regla #4).
- ``UserUpdate`` sin ``time_zone`` lo deja en ``None`` (PATCH parcial, no toca el huso).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.user import UserBase, UserUpdate


def test_userbase_time_zone_defaults_to_utc() -> None:
    """Sin ``time_zone`` explícito, ``UserBase`` defaultea a ``UTC``."""
    model = UserBase()
    assert model.time_zone == "UTC"


def test_user_update_accepts_valid_iana_tz() -> None:
    """Un identificador IANA real pasa la validación y se conserva."""
    model = UserUpdate(time_zone="America/Argentina/Buenos_Aires")
    assert model.time_zone == "America/Argentina/Buenos_Aires"


def test_user_update_accepts_utc() -> None:
    """``UTC`` es un huso válido."""
    assert UserUpdate(time_zone="UTC").time_zone == "UTC"


def test_user_update_none_time_zone_is_noop() -> None:
    """``UserUpdate`` sin ``time_zone`` lo deja en ``None`` (PATCH parcial)."""
    model = UserUpdate(display_name="Mateo")
    assert model.time_zone is None


@pytest.mark.parametrize("bad_tz", ["UTC+3", "Argentina", "Mars/Phobos", "no-es-un-huso", ""])
def test_user_update_rejects_invalid_iana_tz(bad_tz: str) -> None:
    """Un ``time_zone`` que no es IANA real → ``ValidationError`` (FastAPI: 422)."""
    with pytest.raises(ValidationError) as exc_info:
        UserUpdate(time_zone=bad_tz)
    errors = exc_info.value.errors()
    # El tipo de error es el custom estable (no un ValueError genérico filtrado).
    tz_errors = [err for err in errors if err["type"] == "invalid_time_zone"]
    assert tz_errors
    # Regla #4: el MENSAJE del error custom NO arrastra el valor inválido del usuario
    # (Pydantic igual adjunta ``input`` por su cuenta; lo que controlamos es nuestro msg).
    if bad_tz:
        assert all(bad_tz not in err["msg"] for err in tz_errors)
