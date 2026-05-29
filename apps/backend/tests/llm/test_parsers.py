"""Tests del normalizador de tool calls OpenAI (M2).

Tabla de fixtures: tool_call bien formado, arguments JSON invalido (->
ToolParsingError), multiples tool_calls, y acumulacion de fragmentos de
streaming.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.llm.clients.parsers import OpenAIToolCallParser
from app.llm.errors import ToolParsingError

_FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> Any:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def parser() -> OpenAIToolCallParser:
    return OpenAIToolCallParser()


# ---------- parse (no streaming) ----------


def test_parse_no_tool_calls(parser: OpenAIToolCallParser) -> None:
    body = _load("completion_text.json")
    message = body["choices"][0]["message"]
    assert parser.parse(message) == []


def test_parse_single_tool_call(parser: OpenAIToolCallParser) -> None:
    body = _load("completion_tool_call.json")
    message = body["choices"][0]["message"]
    calls = parser.parse(message)
    assert len(calls) == 1
    assert calls[0].id == "call_abc123"
    assert calls[0].name == "get_weather"
    assert calls[0].arguments == {"city": "Buenos Aires", "units": "celsius"}


def test_parse_multiple_tool_calls(parser: OpenAIToolCallParser) -> None:
    body = _load("completion_multi_tool_call.json")
    message = body["choices"][0]["message"]
    calls = parser.parse(message)
    assert [c.name for c in calls] == ["get_weather", "create_reminder"]
    assert calls[0].arguments == {"city": "Cordoba"}
    assert calls[1].arguments["text"] == "comprar pan"


def test_parse_bad_arguments_raises(parser: OpenAIToolCallParser) -> None:
    body = _load("completion_bad_arguments.json")
    message = body["choices"][0]["message"]
    with pytest.raises(ToolParsingError, match="JSON"):
        parser.parse(message)


def test_parse_missing_name_raises(parser: OpenAIToolCallParser) -> None:
    message = {"tool_calls": [{"id": "x", "type": "function", "function": {"arguments": "{}"}}]}
    with pytest.raises(ToolParsingError, match=r"function\.name"):
        parser.parse(message)


def test_parse_missing_function_raises(parser: OpenAIToolCallParser) -> None:
    message = {"tool_calls": [{"id": "x", "type": "function"}]}
    with pytest.raises(ToolParsingError, match="function"):
        parser.parse(message)


def test_parse_empty_arguments_to_empty_dict(parser: OpenAIToolCallParser) -> None:
    message = {
        "tool_calls": [{"id": "x", "type": "function", "function": {"name": "f", "arguments": ""}}]
    }
    calls = parser.parse(message)
    assert calls[0].arguments == {}


def test_parse_id_falls_back_to_name(parser: OpenAIToolCallParser) -> None:
    message = {"tool_calls": [{"type": "function", "function": {"name": "f", "arguments": "{}"}}]}
    calls = parser.parse(message)
    assert calls[0].id == "f"


def test_parse_tool_calls_not_list_raises(parser: OpenAIToolCallParser) -> None:
    with pytest.raises(ToolParsingError, match="lista"):
        parser.parse({"tool_calls": "nope"})


# ---------- accumulate (streaming) ----------


def test_accumulate_single_tool_call(parser: OpenAIToolCallParser) -> None:
    deltas = _load("stream_tool_call_deltas.json")
    calls = parser.accumulate(deltas)
    assert len(calls) == 1
    assert calls[0].id == "call_stream_1"
    assert calls[0].name == "get_weather"
    assert calls[0].arguments == {"city": "Rosario"}


def test_accumulate_multiple_indices(parser: OpenAIToolCallParser) -> None:
    deltas = [
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "c0",
                                "function": {"name": "a", "arguments": '{"x":'},
                            },
                            {
                                "index": 1,
                                "id": "c1",
                                "function": {"name": "b", "arguments": '{"y":'},
                            },
                        ]
                    },
                }
            ]
        },
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "function": {"arguments": "1}"}},
                            {"index": 1, "function": {"arguments": "2}"}},
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        },
    ]
    calls = parser.accumulate(deltas)
    assert [c.name for c in calls] == ["a", "b"]
    assert calls[0].arguments == {"x": 1}
    assert calls[1].arguments == {"y": 2}


def test_accumulate_empty_stream(parser: OpenAIToolCallParser) -> None:
    assert parser.accumulate([]) == []


def test_accumulate_bad_json_raises(parser: OpenAIToolCallParser) -> None:
    deltas = [
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "id": "c", "function": {"name": "f", "arguments": "{bad"}}
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }
    ]
    with pytest.raises(ToolParsingError, match="JSON"):
        parser.accumulate(deltas)
