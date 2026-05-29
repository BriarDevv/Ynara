"""Tests de los schemas de la capa LLM (M1).

Verifican que strict valida lo correcto y rechaza lo incoherente, y que
los resultados inmutables (``frozen``) no se puedan mutar.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.enums import Mode
from app.llm.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    CompletionChunk,
    CompletionResult,
    ModelHealth,
    ToolCall,
    ToolSpec,
)


class TestChatMessage:
    def test_valid_user_message(self) -> None:
        m = ChatMessage(role="user", content="hola")
        assert m.role == "user"
        assert m.tool_call_id is None

    def test_assistant_without_content_ok(self) -> None:
        m = ChatMessage(role="assistant", content=None)
        assert m.content is None

    def test_tool_message_with_ids(self) -> None:
        m = ChatMessage(role="tool", content="42", tool_call_id="abc", name="calc")
        assert m.tool_call_id == "abc"
        assert m.name == "calc"

    def test_invalid_role_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChatMessage(role="root", content="x")  # type: ignore[arg-type]

    def test_strict_rejects_int_content(self) -> None:
        with pytest.raises(ValidationError):
            ChatMessage(role="user", content=123)  # type: ignore[arg-type]


class TestToolSpec:
    def test_valid(self) -> None:
        spec = ToolSpec(
            name="get_weather",
            description="clima de una ciudad",
            parameters={"type": "object", "properties": {}},
        )
        assert spec.name == "get_weather"

    def test_parameters_must_be_dict(self) -> None:
        with pytest.raises(ValidationError):
            ToolSpec(name="x", description="y", parameters="no")  # type: ignore[arg-type]


class TestToolCall:
    def test_arguments_already_parsed(self) -> None:
        tc = ToolCall(id="call_1", name="calc", arguments={"a": 1, "b": 2})
        assert tc.arguments == {"a": 1, "b": 2}

    def test_frozen(self) -> None:
        tc = ToolCall(id="call_1", name="calc", arguments={})
        with pytest.raises(ValidationError):
            tc.name = "otro"  # type: ignore[misc]

    def test_arguments_must_be_dict(self) -> None:
        with pytest.raises(ValidationError):
            ToolCall(id="x", name="y", arguments="{}")  # type: ignore[arg-type]


class TestCompletionResult:
    def test_valid_text_only(self) -> None:
        r = CompletionResult(
            text="hola",
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=5,
            model_name="qwen-3.5-9b",
            latency_ms=42.0,
        )
        assert r.tool_calls == []
        assert r.finish_reason == "stop"

    def test_with_tool_calls(self) -> None:
        r = CompletionResult(
            text="",
            tool_calls=[ToolCall(id="c1", name="calc", arguments={"x": 1})],
            finish_reason="tool_calls",
            prompt_tokens=1,
            completion_tokens=1,
            model_name="qwen-3.5-9b",
            latency_ms=1.0,
        )
        assert r.tool_calls[0].name == "calc"

    def test_frozen(self) -> None:
        r = CompletionResult(
            text="x",
            finish_reason="stop",
            prompt_tokens=1,
            completion_tokens=1,
            model_name="m",
            latency_ms=1.0,
        )
        with pytest.raises(ValidationError):
            r.text = "otro"  # type: ignore[misc]

    def test_strict_rejects_str_tokens(self) -> None:
        with pytest.raises(ValidationError):
            CompletionResult(
                text="x",
                finish_reason="stop",
                prompt_tokens="10",  # type: ignore[arg-type]
                completion_tokens=1,
                model_name="m",
                latency_ms=1.0,
            )


class TestCompletionChunk:
    def test_minimal(self) -> None:
        c = CompletionChunk(delta_text="ho")
        assert c.tool_call_delta is None
        assert c.finish_reason is None

    def test_with_finish_reason(self) -> None:
        c = CompletionChunk(delta_text="", finish_reason="stop")
        assert c.finish_reason == "stop"

    def test_frozen(self) -> None:
        c = CompletionChunk(delta_text="x")
        with pytest.raises(ValidationError):
            c.delta_text = "y"  # type: ignore[misc]


class TestModelHealth:
    def test_valid(self) -> None:
        h = ModelHealth(model_name="qwen-3.5-9b", healthy=True)
        assert h.healthy is True

    def test_strict_rejects_non_bool(self) -> None:
        with pytest.raises(ValidationError):
            ModelHealth(model_name="m", healthy="yes")  # type: ignore[arg-type]


class TestRouterContract:
    def test_chat_request(self) -> None:
        req = ChatRequest(text="hola", mode=Mode.PRODUCTIVIDAD)
        assert req.mode is Mode.PRODUCTIVIDAD
        assert req.session_id is None

    def test_chat_response_defaults(self) -> None:
        resp = ChatResponse(text="hola", session_id="s1")
        assert resp.actions == []
