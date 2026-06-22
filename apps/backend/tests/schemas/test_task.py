"""Tests Pydantic puros (sin DB) de los schemas del dominio TAREAS (Fase D1).

Cubre ``TaskOut`` / ``TaskCreate`` / ``TaskPatch`` (en ``app/schemas/task.py``) y el
envelope ``TasksResponse`` (``app/schemas/task_api.py``).

Espeja el contrato de ``packages/shared-schemas/src/today.ts`` ("Pydantic gana, Zod
sigue"): mismos campos, mismas validaciones (``title`` min 1, ``duration_min`` > 0 y
nullable, ``scheduled_at`` nullable). A diferencia de Agenda NO hay invariante entre
campos.

GOTCHA STRICT (mismo que el resto de schemas Ynara): ``YnaraBaseModel`` usa
``strict=True``. Bajo construcción Python/dict los timestamps deben ser ``datetime``
reales y los ids ``UUID`` reales; el path JSON (``model_validate_json``) sí coerciona
los wire types (str ISO → datetime, str UUID → UUID), que es como entra el body real.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.enums import TaskStatus
from app.schemas.task import TaskCreate, TaskOut, TaskPatch
from app.schemas.task_api import TasksResponse


def _out_kwargs() -> dict[str, object]:
    """Kwargs válidos (tipos concretos, strict-friendly) para un ``TaskOut``."""
    return {
        "id": uuid4(),
        "title": "Llamar al dentista",
        "status": TaskStatus.PENDING,
        "scheduled_at": datetime(2026, 6, 22, 14, 0, 0, tzinfo=UTC),
        "duration_min": 45,
    }


# ---------- TaskOut ----------


class TestTaskOut:
    def test_valid_construction_from_dict(self) -> None:
        kwargs = _out_kwargs()
        task = TaskOut.model_validate(kwargs)
        assert task.id == kwargs["id"]
        assert task.title == "Llamar al dentista"
        assert task.status == TaskStatus.PENDING
        assert task.duration_min == 45

    def test_json_serialization_has_expected_fields(self) -> None:
        """El wire shape NO incluye user_id / created_at / updated_at."""
        task = TaskOut.model_validate(_out_kwargs())
        data = task.model_dump(mode="json")
        assert set(data) == {"id", "title", "status", "scheduled_at", "duration_min"}
        assert "user_id" not in data
        assert "created_at" not in data
        assert "updated_at" not in data
        # StrEnum por su .value.
        assert data["status"] == TaskStatus.PENDING.value == "pending"

    def test_json_roundtrip(self) -> None:
        task = TaskOut.model_validate(_out_kwargs())
        restored = TaskOut.model_validate_json(task.model_dump_json())
        assert restored == task

    @pytest.mark.parametrize("st", list(TaskStatus))
    def test_all_statuses_accepted(self, st: TaskStatus) -> None:
        kwargs = _out_kwargs()
        kwargs["status"] = st
        task = TaskOut.model_validate(kwargs)
        assert task.status == st

    def test_scheduled_at_nullable(self) -> None:
        kwargs = _out_kwargs()
        kwargs["scheduled_at"] = None
        task = TaskOut.model_validate(kwargs)
        assert task.scheduled_at is None

    def test_duration_min_nullable(self) -> None:
        kwargs = _out_kwargs()
        kwargs["duration_min"] = None
        task = TaskOut.model_validate(kwargs)
        assert task.duration_min is None

    def test_empty_title_rejected(self) -> None:
        kwargs = _out_kwargs()
        kwargs["title"] = ""
        with pytest.raises(ValidationError):
            TaskOut.model_validate(kwargs)

    def test_non_positive_duration_rejected(self) -> None:
        kwargs = _out_kwargs()
        kwargs["duration_min"] = 0
        with pytest.raises(ValidationError):
            TaskOut.model_validate(kwargs)

    def test_extra_field_rejected(self) -> None:
        kwargs = _out_kwargs()
        kwargs["user_id"] = uuid4()  # no es campo del Out: extra=forbid lo rechaza.
        with pytest.raises(ValidationError):
            TaskOut.model_validate(kwargs)

    def test_json_mode_coerces_wire_types(self) -> None:
        """Vía JSON (path real del wire) str ISO/UUID/enum se coercionan."""
        tid = uuid4()
        payload = {
            "id": str(tid),
            "title": "Estudiar",
            "status": "done",
            "scheduled_at": "2026-06-22T09:00:00+00:00",
            "duration_min": 30,
        }
        task = TaskOut.model_validate_json(json.dumps(payload))
        assert task.id == tid
        assert task.status == TaskStatus.DONE
        assert isinstance(task.scheduled_at, datetime)


# ---------- TaskCreate ----------


class TestTaskCreate:
    def test_minimal_valid(self) -> None:
        """Form mínimo (solo title): scheduled_at/duration_min defaultean a null."""
        create = TaskCreate.model_validate_json(json.dumps({"title": "Mínimo"}))
        assert create.title == "Mínimo"
        assert create.scheduled_at is None
        assert create.duration_min is None
        # status NO es campo del create (lo fija el server).
        assert not hasattr(create, "status")

    def test_status_not_accepted(self) -> None:
        """``status`` no es seteable desde el body (extra=forbid)."""
        payload = {"title": "x", "status": "done"}
        with pytest.raises(ValidationError):
            TaskCreate.model_validate_json(json.dumps(payload))

    def test_with_schedule_ok(self) -> None:
        payload = {
            "title": "Reunión",
            "scheduled_at": "2026-06-22T14:00:00+00:00",
            "duration_min": 45,
        }
        create = TaskCreate.model_validate_json(json.dumps(payload))
        assert create.duration_min == 45
        assert isinstance(create.scheduled_at, datetime)

    @pytest.mark.parametrize("bad_duration", [0, -1])
    def test_non_positive_duration_rejected(self, bad_duration: int) -> None:
        payload = {"title": "x", "duration_min": bad_duration}
        with pytest.raises(ValidationError):
            TaskCreate.model_validate_json(json.dumps(payload))

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaskCreate.model_validate_json(json.dumps({"title": ""}))


# ---------- TaskPatch ----------


class TestTaskPatch:
    def test_status_required(self) -> None:
        """El patch togglea status: es REQUERIDO (no es un patch parcial multi-campo)."""
        with pytest.raises(ValidationError):
            TaskPatch.model_validate({})

    def test_patch_status_accepted_via_json(self) -> None:
        """Vía JSON (path real del wire): strict=True coerciona str→enum por JSON."""
        patch = TaskPatch.model_validate_json(json.dumps({"status": "done"}))
        assert patch.status == TaskStatus.DONE

    @pytest.mark.parametrize("st", list(TaskStatus))
    def test_all_statuses_accepted(self, st: TaskStatus) -> None:
        patch = TaskPatch.model_validate_json(json.dumps({"status": st.value}))
        assert patch.status == st

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaskPatch.model_validate_json(json.dumps({"status": "done", "title": "x"}))

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaskPatch.model_validate_json(json.dumps({"status": "garbage"}))


# ---------- TasksResponse ----------


class TestTasksResponse:
    def test_valid_empty(self) -> None:
        resp = TasksResponse.model_validate({"items": [], "total": 0})
        assert resp.items == []
        assert resp.total == 0

    def test_valid_with_items(self) -> None:
        t1 = TaskOut.model_validate(_out_kwargs())
        t2 = TaskOut.model_validate(_out_kwargs())
        resp = TasksResponse.model_validate({"items": [t1, t2], "total": 5})
        assert len(resp.items) == 2
        assert resp.total == 5

    def test_json_serialization_shape(self) -> None:
        t1 = TaskOut.model_validate(_out_kwargs())
        resp = TasksResponse.model_validate({"items": [t1], "total": 1})
        data = resp.model_dump(mode="json")
        assert set(data) == {"items", "total"}
        assert isinstance(data["items"], list)
        assert "user_id" not in data["items"][0]

    def test_items_built_from_dicts(self) -> None:
        resp = TasksResponse.model_validate({"items": [_out_kwargs()], "total": 1})
        assert isinstance(resp.items[0], TaskOut)

    def test_json_roundtrip(self) -> None:
        t1 = TaskOut.model_validate(_out_kwargs())
        resp = TasksResponse.model_validate({"items": [t1], "total": 3})
        restored = TasksResponse.model_validate_json(resp.model_dump_json())
        assert restored == resp

    def test_total_required(self) -> None:
        with pytest.raises(ValidationError):
            TasksResponse.model_validate({"items": []})

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TasksResponse.model_validate({"items": [], "total": 0, "page": 1})
