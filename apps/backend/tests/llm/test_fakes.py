"""Tests del ``FakeLlmClient`` programable (M2).

Confirma que satisface el Protocol ``LLMClient`` y que la programacion de
resultados / errores / chunks funciona, para que sirva como doble en los
tests del router y del pool (M3+).
"""

from __future__ import annotations

import pytest

from app.llm.clients.base import LLMClient
from app.llm.clients.fakes import FakeLlmClient
from app.llm.errors import LlmTimeoutError
from app.llm.schemas import ChatMessage, CompletionChunk, CompletionResult

_MODEL = "qwen-3.5-9b"


def _result(text: str = "ok") -> CompletionResult:
    return CompletionResult(
        text=text,
        finish_reason="stop",
        prompt_tokens=1,
        completion_tokens=1,
        model_name=_MODEL,
        latency_ms=0.0,
    )


def _messages() -> list[ChatMessage]:
    return [ChatMessage(role="user", content="hola")]


def test_satisfies_protocol() -> None:
    fake = FakeLlmClient(served_models=frozenset({_MODEL}))
    assert isinstance(fake, LLMClient)


def test_serves_model() -> None:
    fake = FakeLlmClient(served_models=frozenset({_MODEL}))
    assert fake.serves_model(_MODEL)
    assert not fake.serves_model("otro")


@pytest.mark.asyncio
async def test_complete_returns_queued_result() -> None:
    fake = FakeLlmClient(served_models=frozenset({_MODEL}))
    fake.queue_result(_result("hola"))
    result = await fake.complete(model=_MODEL, messages=_messages())
    assert result.text == "hola"
    assert fake.complete_calls[0]["model"] == _MODEL


@pytest.mark.asyncio
async def test_complete_raises_queued_error() -> None:
    fake = FakeLlmClient(served_models=frozenset({_MODEL}))
    fake.queue_error(LlmTimeoutError())
    with pytest.raises(LlmTimeoutError):
        await fake.complete(model=_MODEL, messages=_messages())


@pytest.mark.asyncio
async def test_complete_without_program_raises() -> None:
    fake = FakeLlmClient(served_models=frozenset({_MODEL}))
    with pytest.raises(AssertionError):
        await fake.complete(model=_MODEL, messages=_messages())


@pytest.mark.asyncio
async def test_stream_yields_queued_chunks() -> None:
    fake = FakeLlmClient(served_models=frozenset({_MODEL}))
    fake.queue_chunks([CompletionChunk(delta_text="ho"), CompletionChunk(delta_text="la")])
    chunks = [c async for c in fake.stream(model=_MODEL, messages=_messages())]
    assert "".join(c.delta_text for c in chunks) == "hola"


@pytest.mark.asyncio
async def test_health_toggle() -> None:
    fake = FakeLlmClient(served_models=frozenset({_MODEL}))
    assert (await fake.health()).healthy is True
    fake.set_health(False)
    assert (await fake.health()).healthy is False
