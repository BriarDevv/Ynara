"""Tests Pydantic puros (sin DB) para los schemas HTTP del chat.

Cubre:
- Validaciones de texto (min_length, max_length).
- Validacion de session_id UUID (invalido -> error).
- Round-trip de Action (id, name, arguments, result).
- Comportamiento de strict mode con mode:str y session_id:str-UUID.

GOTCHA STRICT (documentado aqui):
    ``YnaraBaseModel`` usa ``strict=True``. Bajo construccion Python:
        - ``mode='productividad'`` (str) -> RECHAZADO (is_instance_of).
        - ``session_id='<uuid-valido>'`` (str) -> RECHAZADO (is_instance_of).
    Bajo deserializacion JSON (``model_validate_json`` / FastAPI body):
        - ``mode='productividad'`` -> ACEPTADO y casteado a Mode.
        - ``session_id='<uuid-valido>'`` -> ACEPTADO y casteado a UUID.
    Este es el comportamiento correcto: el front manda JSON, FastAPI
    usa el path json-mode (lax para wire types). Los callers Python
    internos deben pasar tipos concretos (Mode enum, UUID object).
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.enums import Mode
from app.schemas.chat import (
    CHAT_TEXT_MAX_LENGTH,
    Action,
    ChatHttpRequest,
    ChatHttpResponse,
)

# ---------- ChatHttpRequest ----------


class TestChatHttpRequest:
    def test_valid_minimal(self) -> None:
        req = ChatHttpRequest(text="hola", mode=Mode.PRODUCTIVIDAD)
        assert req.text == "hola"
        assert req.mode == Mode.PRODUCTIVIDAD
        assert req.session_id is None

    def test_valid_with_session_id(self) -> None:
        sid = uuid4()
        req = ChatHttpRequest(text="hola", mode=Mode.ESTUDIO, session_id=sid)
        assert req.session_id == sid

    def test_text_empty_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChatHttpRequest(text="", mode=Mode.PRODUCTIVIDAD)

    def test_text_over_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChatHttpRequest(text="x" * (CHAT_TEXT_MAX_LENGTH + 1), mode=Mode.PRODUCTIVIDAD)

    def test_text_exactly_max_accepted(self) -> None:
        req = ChatHttpRequest(text="x" * CHAT_TEXT_MAX_LENGTH, mode=Mode.PRODUCTIVIDAD)
        assert len(req.text) == CHAT_TEXT_MAX_LENGTH

    def test_text_exactly_one_accepted(self) -> None:
        req = ChatHttpRequest(text="a", mode=Mode.PRODUCTIVIDAD)
        assert req.text == "a"

    @pytest.mark.parametrize("mode", list(Mode))
    def test_all_modes_accepted(self, mode: Mode) -> None:
        req = ChatHttpRequest(text="x", mode=mode)
        assert req.mode == mode

    def test_extra_field_rejected(self) -> None:
        """YnaraBaseModel.extra=forbid debe rechazar campos no declarados."""
        with pytest.raises(ValidationError):
            ChatHttpRequest(text="x", mode=Mode.PRODUCTIVIDAD, garbage="bad")  # type: ignore[call-arg]

    # --- coercion de wire types (strict=False en el request) ---
    # ChatHttpRequest relaja strict (a diferencia del resto de schemas) porque
    # FastAPI valida el body con model_validate(dict) -> bajo strict=True un
    # str 'productividad' NO es instancia de Mode y el front recibiria un 422
    # por mandar el wire documentado. Estos tests fijan la coercion correcta.

    def test_str_mode_coerced_via_python_construction(self) -> None:
        """strict=False: str 'productividad' se coerciona a Mode (wire del front)."""
        req = ChatHttpRequest(text="x", mode="productividad")  # type: ignore[arg-type]
        assert req.mode == Mode.PRODUCTIVIDAD

    def test_str_session_id_coerced_via_python_construction(self) -> None:
        """strict=False: str UUID valido se coerciona a UUID (wire del front)."""
        sid = "01234567-89ab-cdef-0123-456789abcdef"
        req = ChatHttpRequest(
            text="x",
            mode=Mode.PRODUCTIVIDAD,
            session_id=sid,  # type: ignore[arg-type]
        )
        assert req.session_id == UUID(sid)

    def test_json_mode_str_mode_and_uuid_accepted(self) -> None:
        """Via model_validate(dict)/JSON (path FastAPI) str->Mode y str->UUID se aceptan.

        El front manda JSON; FastAPI parsea a dict y valida con model_validate.
        Con strict=False el request coerciona los wire types (str->UUID,
        str->StrEnum) sin filtrar basura (las constraints siguen).
        """
        sid = "01234567-89ab-cdef-0123-456789abcdef"
        payload = json.dumps({"text": "hola", "mode": "productividad", "session_id": sid})
        req = ChatHttpRequest.model_validate_json(payload)
        assert req.mode == Mode.PRODUCTIVIDAD
        assert req.session_id == UUID(sid)
        # Y por el path real de FastAPI (dict ya parseado), no solo bytes JSON.
        req2 = ChatHttpRequest.model_validate(
            {"text": "hola", "mode": "productividad", "session_id": sid}
        )
        assert req2.mode == Mode.PRODUCTIVIDAD
        assert req2.session_id == UUID(sid)

    def test_json_mode_invalid_session_id_rejected(self) -> None:
        """Un session_id que no es UUID valido se rechaza incluso via JSON."""
        payload = json.dumps({"text": "hola", "mode": "productividad", "session_id": "not-a-uuid"})
        with pytest.raises(ValidationError):
            ChatHttpRequest.model_validate_json(payload)

    def test_json_mode_invalid_mode_rejected(self) -> None:
        """Un mode no reconocido se rechaza via JSON."""
        payload = json.dumps({"text": "hola", "mode": "nonexistent_mode"})
        with pytest.raises(ValidationError):
            ChatHttpRequest.model_validate_json(payload)

    def test_json_mode_session_id_absent_accepted(self) -> None:
        """session_id ausente en JSON es valido (Optional)."""
        payload = json.dumps({"text": "hola", "mode": "productividad"})
        req = ChatHttpRequest.model_validate_json(payload)
        assert req.session_id is None

    def test_json_mode_session_id_null_accepted(self) -> None:
        """session_id=null en JSON es valido (Optional)."""
        payload = json.dumps({"text": "hola", "mode": "productividad", "session_id": None})
        req = ChatHttpRequest.model_validate_json(payload)
        assert req.session_id is None


# ---------- Action ----------


class TestAction:
    def test_valid_full(self) -> None:
        action = Action(
            id="call_123",
            name="memory.search",
            arguments={"query": "preferencias"},
            result={"results": []},
        )
        assert action.id == "call_123"
        assert action.name == "memory.search"
        assert action.arguments == {"query": "preferencias"}
        assert action.result == {"results": []}

    def test_arguments_defaults_to_empty_dict(self) -> None:
        action = Action(id="x", name="tool.foo")
        assert action.arguments == {}

    def test_result_defaults_to_empty_dict(self) -> None:
        action = Action(id="x", name="tool.foo")
        assert action.result == {}

    def test_round_trip_json(self) -> None:
        """Serializar y deserializar via JSON conserva todos los campos."""
        action = Action(
            id="call_abc",
            name="calendar.create",
            arguments={"title": "Reunion", "date": "2026-06-01"},
            result={"event_id": "evt_xyz", "status": "created"},
        )
        dumped = action.model_dump_json()
        restored = Action.model_validate_json(dumped)
        assert restored == action

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Action(id="x", name="y", unknown_field="z")  # type: ignore[call-arg]

    def test_id_required(self) -> None:
        with pytest.raises(ValidationError):
            Action(name="tool.foo")  # type: ignore[call-arg]

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            Action(id="call_1")  # type: ignore[call-arg]


# ---------- ChatHttpResponse ----------


class TestChatHttpResponse:
    def test_valid_minimal(self) -> None:
        resp = ChatHttpResponse(text="hola", session_id=uuid4())
        assert resp.actions == []
        assert resp.finish_reason is None

    def test_valid_with_actions(self) -> None:
        sid = uuid4()
        actions = [Action(id="c1", name="memory.search", result={"results": []})]
        resp = ChatHttpResponse(
            text="resultado",
            actions=actions,
            session_id=sid,
            finish_reason="stop",
        )
        assert len(resp.actions) == 1
        assert resp.actions[0].name == "memory.search"
        assert resp.finish_reason == "stop"

    def test_session_id_required(self) -> None:
        with pytest.raises(ValidationError):
            ChatHttpResponse(text="x")  # type: ignore[call-arg]

    def test_text_required(self) -> None:
        with pytest.raises(ValidationError):
            ChatHttpResponse(session_id=uuid4())  # type: ignore[call-arg]

    def test_finish_reason_none_accepted(self) -> None:
        resp = ChatHttpResponse(text="x", session_id=uuid4(), finish_reason=None)
        assert resp.finish_reason is None

    def test_finish_reason_degraded_accepted(self) -> None:
        resp = ChatHttpResponse(text="x", session_id=uuid4(), finish_reason="degraded")
        assert resp.finish_reason == "degraded"

    def test_json_roundtrip_session_id_serializes_as_string(self) -> None:
        """UUID se serializa como string en JSON (compatible con chat.ts)."""
        sid = uuid4()
        resp = ChatHttpResponse(text="x", session_id=sid)
        data = resp.model_dump(mode="json")
        assert isinstance(data["session_id"], str)
        assert data["session_id"] == str(sid)

    def test_json_mode_str_session_id_accepted(self) -> None:
        """Via JSON el front puede mandar session_id como string UUID."""
        sid = uuid4()
        payload = json.dumps({"text": "x", "session_id": str(sid), "actions": []})
        resp = ChatHttpResponse.model_validate_json(payload)
        assert resp.session_id == sid

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChatHttpResponse(text="x", session_id=uuid4(), extra_key="bad")  # type: ignore[call-arg]
