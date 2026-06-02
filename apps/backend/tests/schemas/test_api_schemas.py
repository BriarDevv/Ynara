"""Tests Pydantic puros (sin DB) para los schemas de respuesta de la API.

Cubre los *envelopes* de wire HTTP que NO espejan tablas:

- ``SessionOut`` (``app/schemas/session.py``): la sesión serializada.
- ``SessionListPage`` (``app/schemas/session_api.py``): la página de sesiones
  (``items`` + ``total``) de ``GET /v1/sessions``.
- ``TokenOut`` (``app/schemas/auth.py``): el response de ``/auth/token`` y
  ``/auth/refresh`` (access_token + token_type + refresh_token opcional, issue #63).

NOTA DE NOMBRES (vs. la consigna):
    El task pedía ``SessionListOut``, pero el envelope real se llama
    ``SessionListPage`` y NO trae objeto de paginación: solo ``items``
    (``list[SessionOut]``) + ``total`` (int). Asimismo ``TokenOut.refresh_token``
    es **opcional** (default ``None``, additive/non-breaking), no obligatorio:
    los tests fijan que serializa cuando está presente y que defaultea a ``None``.

GOTCHA STRICT (mismo que el resto de schemas Ynara):
    ``YnaraBaseModel`` usa ``strict=True``. Bajo construcción Python / dict los
    timestamps deben ser ``datetime`` reales y los ids ``UUID`` reales (un str
    UUID o ISO se rechaza). El path JSON (``model_validate_json``) sí coerciona
    los wire types (str ISO -> datetime, str UUID -> UUID), que es como entra el
    body real; ambos paths están cubiertos.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.enums import Mode
from app.schemas.auth import TokenOut
from app.schemas.session import SessionOut
from app.schemas.session_api import SessionListPage


def _session_kwargs() -> dict[str, object]:
    """Kwargs válidos (tipos concretos, strict-friendly) para un ``SessionOut``."""
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    return {
        "id": uuid4(),
        "user_id": uuid4(),
        "mode": Mode.PRODUCTIVIDAD,
        "started_at": now,
        "ended_at": None,
        "created_at": now,
        "updated_at": now,
    }


# ---------- SessionOut ----------


class TestSessionOut:
    def test_valid_construction_from_dict(self) -> None:
        kwargs = _session_kwargs()
        session = SessionOut.model_validate(kwargs)
        assert session.id == kwargs["id"]
        assert session.user_id == kwargs["user_id"]
        assert session.mode == Mode.PRODUCTIVIDAD
        assert session.started_at == kwargs["started_at"]
        assert session.ended_at is None
        assert session.created_at == kwargs["created_at"]
        assert session.updated_at == kwargs["updated_at"]

    def test_ended_at_can_be_set(self) -> None:
        kwargs = _session_kwargs()
        ended = datetime(2026, 6, 1, 13, 0, 0, tzinfo=UTC)
        kwargs["ended_at"] = ended
        session = SessionOut.model_validate(kwargs)
        assert session.ended_at == ended

    def test_json_serialization_has_expected_fields(self) -> None:
        kwargs = _session_kwargs()
        session = SessionOut.model_validate(kwargs)
        data = session.model_dump(mode="json")
        assert set(data) == {
            "id",
            "user_id",
            "mode",
            "started_at",
            "ended_at",
            "created_at",
            "updated_at",
        }
        # UUIDs y datetimes se serializan como strings JSON.
        assert isinstance(data["id"], str)
        assert data["id"] == str(kwargs["id"])
        assert isinstance(data["user_id"], str)
        assert data["user_id"] == str(kwargs["user_id"])
        # StrEnum se serializa por su .value.
        assert data["mode"] == Mode.PRODUCTIVIDAD.value == "productividad"
        assert isinstance(data["started_at"], str)
        assert data["ended_at"] is None

    def test_json_roundtrip(self) -> None:
        session = SessionOut.model_validate(_session_kwargs())
        restored = SessionOut.model_validate_json(session.model_dump_json())
        assert restored == session

    @pytest.mark.parametrize("mode", list(Mode))
    def test_all_modes_accepted(self, mode: Mode) -> None:
        kwargs = _session_kwargs()
        kwargs["mode"] = mode
        session = SessionOut.model_validate(kwargs)
        assert session.mode == mode

    def test_missing_required_field_rejected(self) -> None:
        kwargs = _session_kwargs()
        del kwargs["user_id"]
        with pytest.raises(ValidationError):
            SessionOut.model_validate(kwargs)

    def test_wrong_type_rejected(self) -> None:
        """strict=True: un id que no es UUID se rechaza vía construcción dict."""
        kwargs = _session_kwargs()
        kwargs["id"] = 12345  # int, no UUID
        with pytest.raises(ValidationError):
            SessionOut.model_validate(kwargs)

    def test_extra_field_rejected(self) -> None:
        kwargs = _session_kwargs()
        kwargs["garbage"] = "bad"
        with pytest.raises(ValidationError):
            SessionOut.model_validate(kwargs)

    def test_json_mode_coerces_wire_types(self) -> None:
        """Vía JSON (path real del wire) str ISO/UUID/enum se coercionan."""
        sid = uuid4()
        uid = uuid4()
        payload = {
            "id": str(sid),
            "user_id": str(uid),
            "mode": "estudio",
            "started_at": "2026-06-01T12:00:00+00:00",
            "ended_at": None,
            "created_at": "2026-06-01T12:00:00+00:00",
            "updated_at": "2026-06-01T12:00:00+00:00",
        }
        session = SessionOut.model_validate_json(json.dumps(payload))
        assert session.id == sid
        assert session.user_id == uid
        assert session.mode == Mode.ESTUDIO
        assert isinstance(session.started_at, datetime)


# ---------- SessionListPage ----------


class TestSessionListPage:
    def test_valid_empty_page(self) -> None:
        page = SessionListPage.model_validate({"items": [], "total": 0})
        assert page.items == []
        assert page.total == 0

    def test_valid_page_with_items(self) -> None:
        s1 = SessionOut.model_validate(_session_kwargs())
        s2 = SessionOut.model_validate(_session_kwargs())
        page = SessionListPage.model_validate({"items": [s1, s2], "total": 7})
        assert len(page.items) == 2
        assert page.items[0] == s1
        assert page.items[1] == s2
        # total es el conteo COMPLETO del user, no el largo de la página.
        assert page.total == 7

    def test_json_serialization_shape(self) -> None:
        s1 = SessionOut.model_validate(_session_kwargs())
        page = SessionListPage.model_validate({"items": [s1], "total": 1})
        data = page.model_dump(mode="json")
        assert set(data) == {"items", "total"}
        assert isinstance(data["items"], list)
        assert len(data["items"]) == 1
        assert data["total"] == 1
        # Cada item conserva el shape de SessionOut.
        assert set(data["items"][0]) == {
            "id",
            "user_id",
            "mode",
            "started_at",
            "ended_at",
            "created_at",
            "updated_at",
        }

    def test_items_built_from_dicts(self) -> None:
        """``items`` acepta dicts y los valida a SessionOut anidado."""
        page = SessionListPage.model_validate({"items": [_session_kwargs()], "total": 1})
        assert isinstance(page.items[0], SessionOut)

    def test_json_roundtrip(self) -> None:
        s1 = SessionOut.model_validate(_session_kwargs())
        page = SessionListPage.model_validate({"items": [s1], "total": 3})
        restored = SessionListPage.model_validate_json(page.model_dump_json())
        assert restored == page

    def test_total_required(self) -> None:
        with pytest.raises(ValidationError):
            SessionListPage.model_validate({"items": []})

    def test_items_required(self) -> None:
        with pytest.raises(ValidationError):
            SessionListPage.model_validate({"total": 0})

    def test_total_wrong_type_rejected(self) -> None:
        """strict=True: total debe ser int, un str se rechaza vía construcción dict."""
        with pytest.raises(ValidationError):
            SessionListPage.model_validate({"items": [], "total": "many"})

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SessionListPage.model_validate({"items": [], "total": 0, "page": 1})


# ---------- TokenOut ----------


class TestTokenOut:
    def test_valid_full(self) -> None:
        token = TokenOut(
            access_token="access.jwt.value",
            token_type="bearer",
            refresh_token="refresh.opaque.value",
        )
        assert token.access_token == "access.jwt.value"
        assert token.token_type == "bearer"
        assert token.refresh_token == "refresh.opaque.value"

    def test_token_type_defaults_to_bearer(self) -> None:
        token = TokenOut(access_token="a")
        assert token.token_type == "bearer"

    def test_refresh_token_defaults_to_none(self) -> None:
        """``refresh_token`` es additive (issue #63): opcional, default None."""
        token = TokenOut(access_token="a")
        assert token.refresh_token is None

    def test_json_serialization_includes_refresh_token(self) -> None:
        token = TokenOut(
            access_token="access.jwt.value",
            refresh_token="refresh.opaque.value",
        )
        data = token.model_dump(mode="json")
        assert set(data) == {"access_token", "token_type", "refresh_token"}
        assert data["access_token"] == "access.jwt.value"
        assert data["token_type"] == "bearer"
        assert data["refresh_token"] == "refresh.opaque.value"

    def test_json_serialization_refresh_token_none_present(self) -> None:
        """Aun sin refresh_token, el campo se serializa explícito como null."""
        token = TokenOut(access_token="a")
        data = token.model_dump(mode="json")
        assert "refresh_token" in data
        assert data["refresh_token"] is None

    def test_json_roundtrip(self) -> None:
        token = TokenOut(access_token="a", refresh_token="r")
        restored = TokenOut.model_validate_json(token.model_dump_json())
        assert restored == token

    def test_access_token_required(self) -> None:
        with pytest.raises(ValidationError):
            TokenOut(token_type="bearer")  # type: ignore[call-arg]

    def test_token_type_invalid_literal_rejected(self) -> None:
        """token_type es Literal['bearer']: cualquier otro valor se rechaza."""
        with pytest.raises(ValidationError):
            TokenOut(access_token="a", token_type="basic")  # type: ignore[arg-type]

    def test_access_token_wrong_type_rejected(self) -> None:
        """strict=True: access_token debe ser str, un int se rechaza."""
        with pytest.raises(ValidationError):
            TokenOut(access_token=123)  # type: ignore[arg-type]

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TokenOut(access_token="a", expires_in=3600)  # type: ignore[call-arg]
