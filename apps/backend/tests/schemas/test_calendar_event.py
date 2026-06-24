"""Tests Pydantic puros (sin DB) de los schemas del dominio Agenda (ADR-023).

Cubre ``CalendarEventOut`` / ``EventCreate`` / ``EventPatch`` (en
``app/schemas/calendar_event.py``) y el envelope ``EventsResponse``
(``app/schemas/calendar_event_api.py``).

Espeja el contrato de ``packages/shared-schemas/src/agenda.ts`` ("Pydantic gana,
Zod sigue"): mismos campos, mismas validaciones (``title`` min 1, ``duration_min``
> 0) y la invariante ``recurrence`` exige ``time_zone`` (ADR-023) en Out/Create,
NO en el patch parcial.

GOTCHA STRICT (mismo que el resto de schemas Ynara): ``YnaraBaseModel`` usa
``strict=True``. Bajo construcción Python/dict los timestamps deben ser
``datetime`` reales y los ids ``UUID`` reales; el path JSON
(``model_validate_json``) sí coerciona los wire types (str ISO → datetime, str
UUID → UUID), que es como entra el body real.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.enums import EventStatus, Mode
from app.schemas.calendar_event import CalendarEventOut, EventCreate, EventPatch
from app.schemas.calendar_event_api import EventsResponse


def _out_kwargs() -> dict[str, object]:
    """Kwargs válidos (tipos concretos, strict-friendly) para un ``CalendarEventOut``."""
    return {
        "id": uuid4(),
        "title": "Reunión",
        "start_at": datetime(2026, 6, 22, 9, 0, 0, tzinfo=UTC),
        "duration_min": 60,
        "mode": Mode.PRODUCTIVIDAD,
        "status": EventStatus.CONFIRMED,
        "location": "Oficina",
        "time_zone": None,
        "all_day": False,
        "recurrence": None,
    }


# ---------- CalendarEventOut ----------


class TestCalendarEventOut:
    def test_valid_construction_from_dict(self) -> None:
        kwargs = _out_kwargs()
        ev = CalendarEventOut.model_validate(kwargs)
        assert ev.id == kwargs["id"]
        assert ev.title == "Reunión"
        assert ev.duration_min == 60
        assert ev.mode == Mode.PRODUCTIVIDAD
        assert ev.status == EventStatus.CONFIRMED
        assert ev.all_day is False
        assert ev.recurrence is None

    def test_json_serialization_has_expected_fields(self) -> None:
        """El wire shape NO incluye user_id / created_at / updated_at."""
        ev = CalendarEventOut.model_validate(_out_kwargs())
        data = ev.model_dump(mode="json")
        assert set(data) == {
            "id",
            "title",
            "start_at",
            "duration_min",
            "mode",
            "status",
            "location",
            "time_zone",
            "all_day",
            "recurrence",
        }
        assert "user_id" not in data
        assert "created_at" not in data
        assert "updated_at" not in data
        # StrEnums por su .value.
        assert data["mode"] == Mode.PRODUCTIVIDAD.value
        assert data["status"] == EventStatus.CONFIRMED.value == "confirmed"

    def test_json_roundtrip(self) -> None:
        ev = CalendarEventOut.model_validate(_out_kwargs())
        restored = CalendarEventOut.model_validate_json(ev.model_dump_json())
        assert restored == ev

    @pytest.mark.parametrize("st", list(EventStatus))
    def test_all_statuses_accepted(self, st: EventStatus) -> None:
        kwargs = _out_kwargs()
        kwargs["status"] = st
        ev = CalendarEventOut.model_validate(kwargs)
        assert ev.status == st

    def test_mode_nullable(self) -> None:
        kwargs = _out_kwargs()
        kwargs["mode"] = None
        ev = CalendarEventOut.model_validate(kwargs)
        assert ev.mode is None

    def test_recurrence_without_time_zone_rejected(self) -> None:
        """Invariante ADR-023: recurrence no vacía sin time_zone → ValidationError."""
        kwargs = _out_kwargs()
        kwargs["recurrence"] = ["RRULE:FREQ=WEEKLY"]
        kwargs["time_zone"] = None
        with pytest.raises(ValidationError):
            CalendarEventOut.model_validate(kwargs)

    def test_recurrence_with_time_zone_ok(self) -> None:
        kwargs = _out_kwargs()
        kwargs["recurrence"] = ["RRULE:FREQ=WEEKLY"]
        kwargs["time_zone"] = "America/Argentina/Buenos_Aires"
        ev = CalendarEventOut.model_validate(kwargs)
        assert ev.recurrence == ["RRULE:FREQ=WEEKLY"]

    def test_empty_recurrence_does_not_need_time_zone(self) -> None:
        """recurrence == [] (vacía) NO exige time_zone (igual que el mock del front)."""
        kwargs = _out_kwargs()
        kwargs["recurrence"] = []
        kwargs["time_zone"] = None
        ev = CalendarEventOut.model_validate(kwargs)
        assert ev.recurrence == []

    def test_empty_title_rejected(self) -> None:
        kwargs = _out_kwargs()
        kwargs["title"] = ""
        with pytest.raises(ValidationError):
            CalendarEventOut.model_validate(kwargs)

    def test_non_positive_duration_rejected(self) -> None:
        kwargs = _out_kwargs()
        kwargs["duration_min"] = 0
        with pytest.raises(ValidationError):
            CalendarEventOut.model_validate(kwargs)

    def test_extra_field_rejected(self) -> None:
        kwargs = _out_kwargs()
        kwargs["user_id"] = uuid4()  # no es campo del Out: extra=forbid lo rechaza.
        with pytest.raises(ValidationError):
            CalendarEventOut.model_validate(kwargs)

    def test_json_mode_coerces_wire_types(self) -> None:
        """Vía JSON (path real del wire) str ISO/UUID/enum se coercionan."""
        eid = uuid4()
        payload = {
            "id": str(eid),
            "title": "Estudio",
            "start_at": "2026-06-22T09:00:00+00:00",
            "duration_min": 45,
            "mode": "estudio",
            "status": "tentative",
            "location": None,
            "time_zone": None,
            "all_day": False,
            "recurrence": None,
        }
        ev = CalendarEventOut.model_validate_json(json.dumps(payload))
        assert ev.id == eid
        assert ev.mode == Mode.ESTUDIO
        assert ev.status == EventStatus.TENTATIVE
        assert isinstance(ev.start_at, datetime)


# ---------- EventCreate ----------


class TestEventCreate:
    def test_minimal_valid(self) -> None:
        """Form mínimo: defaults de mode/location/time_zone/recurrence + all_day False."""
        payload = {
            "title": "Mínimo",
            "start_at": "2026-06-22T10:00:00+00:00",
            "duration_min": 30,
        }
        create = EventCreate.model_validate_json(json.dumps(payload))
        assert create.title == "Mínimo"
        assert create.mode is None
        assert create.location is None
        assert create.time_zone is None
        assert create.all_day is False
        assert create.recurrence is None
        # status NO es campo del create (lo fija el server).
        assert not hasattr(create, "status")

    def test_status_not_accepted(self) -> None:
        """``status`` no es seteable desde el body (extra=forbid)."""
        payload = {
            "title": "x",
            "start_at": "2026-06-22T10:00:00+00:00",
            "duration_min": 30,
            "status": "cancelled",
        }
        with pytest.raises(ValidationError):
            EventCreate.model_validate_json(json.dumps(payload))

    def test_recurrence_without_time_zone_rejected(self) -> None:
        payload = {
            "title": "x",
            "start_at": "2026-06-22T10:00:00+00:00",
            "duration_min": 30,
            "recurrence": ["RRULE:FREQ=DAILY"],
        }
        with pytest.raises(ValidationError):
            EventCreate.model_validate_json(json.dumps(payload))

    def test_recurrence_with_time_zone_ok(self) -> None:
        payload = {
            "title": "x",
            "start_at": "2026-06-22T10:00:00+00:00",
            "duration_min": 30,
            "recurrence": ["RRULE:FREQ=DAILY"],
            "time_zone": "America/Argentina/Buenos_Aires",
        }
        create = EventCreate.model_validate_json(json.dumps(payload))
        assert create.recurrence == ["RRULE:FREQ=DAILY"]

    @pytest.mark.parametrize("bad_duration", [0, -1])
    def test_non_positive_duration_rejected(self, bad_duration: int) -> None:
        payload = {
            "title": "x",
            "start_at": "2026-06-22T10:00:00+00:00",
            "duration_min": bad_duration,
        }
        with pytest.raises(ValidationError):
            EventCreate.model_validate_json(json.dumps(payload))

    def test_empty_title_rejected(self) -> None:
        payload = {
            "title": "",
            "start_at": "2026-06-22T10:00:00+00:00",
            "duration_min": 30,
        }
        with pytest.raises(ValidationError):
            EventCreate.model_validate_json(json.dumps(payload))


# ---------- EventPatch ----------


class TestEventPatch:
    def test_all_optional_empty_patch(self) -> None:
        """Un patch vacío es válido; model_fields_set queda vacío (no-op)."""
        patch = EventPatch.model_validate({})
        assert patch.model_dump(exclude_unset=True) == {}

    def test_partial_patch_tracks_set_fields(self) -> None:
        """exclude_unset distingue lo enviado de los defaults (clave del PATCH parcial)."""
        patch = EventPatch.model_validate({"title": "Nuevo"})
        sent = patch.model_dump(exclude_unset=True)
        assert sent == {"title": "Nuevo"}

    def test_patch_does_not_validate_recurrence_invariant(self) -> None:
        """El patch parcial NO valida la invariante recurrence/time_zone (el router sí)."""
        # recurrence sin time_zone en el patch NO lanza acá (es parcial).
        patch = EventPatch.model_validate({"recurrence": ["RRULE:FREQ=WEEKLY"]})
        assert patch.recurrence == ["RRULE:FREQ=WEEKLY"]
        assert patch.time_zone is None

    def test_patch_status_accepted(self) -> None:
        """A diferencia del create, el patch SÍ acepta status.

        Vía JSON (path real del wire): strict=True coerciona str→enum por JSON pero
        NO por dict (mismo gotcha que el resto de schemas Ynara).
        """
        patch = EventPatch.model_validate_json(json.dumps({"status": "cancelled"}))
        assert patch.status == EventStatus.CANCELLED

    def test_patch_empty_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EventPatch.model_validate({"title": ""})

    def test_patch_non_positive_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EventPatch.model_validate({"duration_min": 0})

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EventPatch.model_validate({"garbage": "x"})


# ---------- EventsResponse ----------


class TestEventsResponse:
    def test_valid_empty(self) -> None:
        resp = EventsResponse.model_validate({"items": [], "total": 0})
        assert resp.items == []
        assert resp.total == 0

    def test_valid_with_items(self) -> None:
        e1 = CalendarEventOut.model_validate(_out_kwargs())
        e2 = CalendarEventOut.model_validate(_out_kwargs())
        resp = EventsResponse.model_validate({"items": [e1, e2], "total": 5})
        assert len(resp.items) == 2
        assert resp.total == 5

    def test_json_serialization_shape(self) -> None:
        e1 = CalendarEventOut.model_validate(_out_kwargs())
        resp = EventsResponse.model_validate({"items": [e1], "total": 1})
        data = resp.model_dump(mode="json")
        assert set(data) == {"items", "total"}
        assert isinstance(data["items"], list)
        assert "user_id" not in data["items"][0]

    def test_items_built_from_dicts(self) -> None:
        resp = EventsResponse.model_validate({"items": [_out_kwargs()], "total": 1})
        assert isinstance(resp.items[0], CalendarEventOut)

    def test_json_roundtrip(self) -> None:
        e1 = CalendarEventOut.model_validate(_out_kwargs())
        resp = EventsResponse.model_validate({"items": [e1], "total": 3})
        restored = EventsResponse.model_validate_json(resp.model_dump_json())
        assert restored == resp

    def test_total_required(self) -> None:
        with pytest.raises(ValidationError):
            EventsResponse.model_validate({"items": []})

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EventsResponse.model_validate({"items": [], "total": 0, "page": 1})
