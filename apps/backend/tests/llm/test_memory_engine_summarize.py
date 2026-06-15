"""Tests de ``QwenMemoryEngine.summarize`` + ``_parse_summary`` (issue #209).

UNIT, sin DB ni red. Validan el parseo defensivo del resumen episodico (espejo de
``_parse_ops``): JSON valido -> ``SessionSummary``; JSON corrupto / sin summary /
LLM caido -> ``SessionSummary`` vacio (``summary=''``) sin propagar.
"""

from __future__ import annotations

import json

from app.llm.clients.fakes import FakeLlmClient
from app.llm.memory_engine import QwenMemoryEngine, SessionSummary, _parse_summary
from app.llm.schemas import CompletionResult


def _result(text: str) -> CompletionResult:
    return CompletionResult(
        text=text,
        finish_reason="stop",
        prompt_tokens=5,
        completion_tokens=10,
        model_name="qwen",
        latency_ms=1.0,
    )


# ---------------------------------------------------------------------------
# _parse_summary
# ---------------------------------------------------------------------------


def test_parse_summary_valid() -> None:
    out = _parse_summary(json.dumps({"summary": "El usuario hablo de X.", "topics": {"t": ["X"]}}))
    assert out == SessionSummary(summary="El usuario hablo de X.", topics={"t": ["X"]})


def test_parse_summary_strips_whitespace() -> None:
    out = _parse_summary(json.dumps({"summary": "  resumen  ", "topics": {}}))
    assert out.summary == "resumen"


def test_parse_summary_invalid_json_returns_empty() -> None:
    out = _parse_summary("no soy json {")
    assert out == SessionSummary()
    assert out.summary == ""


def test_parse_summary_not_object_returns_empty() -> None:
    out = _parse_summary(json.dumps(["lista", "no", "objeto"]))
    assert out.summary == ""


def test_parse_summary_missing_summary_returns_empty() -> None:
    out = _parse_summary(json.dumps({"topics": {"t": []}}))
    assert out.summary == ""


def test_parse_summary_strips_think_block() -> None:
    """Un bloque <think>...</think> antes del JSON no rompe el resumen (#235)."""
    raw = "<think>la sesion fue sobre X</think>\n" + json.dumps(
        {"summary": "El usuario hablo de X.", "topics": {"t": ["X"]}}
    )
    out = _parse_summary(raw)
    assert out.summary == "El usuario hablo de X."
    assert out.topics == {"t": ["X"]}


async def test_qwen_engine_summarize_forces_thinking_off() -> None:
    """summarize manda thinking=False (#235): el resumen quiere JSON puro."""
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake_llm.queue_result(_result(json.dumps({"summary": "Hablo de X.", "topics": {}})))
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    await engine.summarize(transcript="user: hola\nmodel: hola!", mode="vida")
    assert fake_llm.complete_calls[0]["thinking"] is False


def test_parse_summary_strips_markdown_fence() -> None:
    """El resumen envuelto en un fence ```json ... ``` se parsea igual (#235)."""
    raw = "```json\n" + json.dumps({"summary": "Resumen.", "topics": {}}) + "\n```"
    out = _parse_summary(raw)
    assert out.summary == "Resumen."


async def test_qwen_engine_summarize_tolerates_think_block() -> None:
    """End-to-end: un bloque <think> en la respuesta no rompe summarize (#235)."""
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    raw = "<think>la sesion fue sobre X</think>\n" + json.dumps(
        {"summary": "El usuario hablo de X.", "topics": {}}
    )
    fake_llm.queue_result(_result(raw))
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    out = await engine.summarize(transcript="user: hola\nmodel: hola!", mode="vida")
    assert out.summary == "El usuario hablo de X."


def test_parse_summary_blank_summary_returns_empty() -> None:
    out = _parse_summary(json.dumps({"summary": "   ", "topics": {}}))
    assert out.summary == ""


def test_parse_summary_topics_not_dict_coerced_to_empty() -> None:
    out = _parse_summary(json.dumps({"summary": "ok", "topics": "malo"}))
    assert out.summary == "ok"
    assert out.topics == {}


# ---------------------------------------------------------------------------
# QwenMemoryEngine.summarize
# ---------------------------------------------------------------------------


async def test_summarize_returns_parsed_summary() -> None:
    client = FakeLlmClient(served_models=frozenset({"qwen"}))
    client.queue_result(_result(json.dumps({"summary": "Resumen de la sesion.", "topics": {}})))
    engine = QwenMemoryEngine(client)

    out = await engine.summarize(transcript="Usuario: hola\nAsistente: hola", mode="vida")
    assert out.summary == "Resumen de la sesion."


async def test_summarize_llm_failure_returns_empty() -> None:
    """Si el LLM lanza, ``summarize`` devuelve un ``SessionSummary`` vacio (no propaga)."""
    client = FakeLlmClient(served_models=frozenset({"qwen"}))
    client.queue_error(RuntimeError("LLM caido"))
    engine = QwenMemoryEngine(client)

    out = await engine.summarize(transcript="Usuario: hola", mode="vida")
    assert out.summary == ""


async def test_summarize_corrupt_json_returns_empty() -> None:
    client = FakeLlmClient(served_models=frozenset({"qwen"}))
    client.queue_result(_result("esto no es json {"))
    engine = QwenMemoryEngine(client)

    out = await engine.summarize(transcript="Usuario: hola", mode="vida")
    assert out.summary == ""
