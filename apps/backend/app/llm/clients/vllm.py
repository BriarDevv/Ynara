"""Cliente HTTP contra un proceso vLLM OpenAI-compatible (M2).

``VllmClient`` habla el endpoint ``/v1/chat/completions`` de un unico
proceso vLLM (un modelo por proceso, ADR-009 D1). Recibe el
``httpx.AsyncClient`` por constructor, asi que es testeable con
``httpx.MockTransport`` sin red real. Nunca importa FastAPI ni vLLM.

Mapeo de errores HTTP a la taxonomia (``app/llm/errors.py``):

- timeout            -> ``LlmTimeoutError``
- ConnectError       -> ``LlmUnavailableError``
- 429                -> ``LlmOverloadedError``
- 400 / 422          -> ``LlmBadRequestError``
- 503                -> ``LlmUnavailableError``
- otros >= 500       -> ``LlmUnavailableError``
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.llm.clients.base import ToolCallParser
from app.llm.errors import (
    LlmBadRequestError,
    LlmError,
    LlmOverloadedError,
    LlmTimeoutError,
    LlmUnavailableError,
    ModelNotServedError,
)
from app.llm.schemas import (
    ChatMessage,
    CompletionChunk,
    CompletionResult,
    ModelHealth,
    ToolSpec,
)

_CHAT_PATH = "/chat/completions"
_MODELS_PATH = "/models"


class VllmClient:
    """Implementa ``LLMClient`` contra un proceso vLLM."""

    def __init__(
        self,
        *,
        base_url: str,
        served_models: frozenset[str],
        http_client: httpx.AsyncClient,
        parser: ToolCallParser,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._served_models = served_models
        self._http = http_client
        self._parser = parser

    def serves_model(self, model: str) -> bool:
        return model in self._served_models

    async def complete(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout_s: float = 30.0,
    ) -> CompletionResult:
        self._ensure_served(model)
        payload = self._build_payload(
            model=model,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False,
        )
        started = time.perf_counter()
        response = await self._post(payload, timeout_s)
        latency_ms = (time.perf_counter() - started) * 1000.0
        self._raise_for_status(response)
        return self._parse_completion(response.json(), model, latency_ms)

    async def stream(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout_s: float = 30.0,
    ) -> AsyncIterator[CompletionChunk]:
        self._ensure_served(model)
        payload = self._build_payload(
            model=model,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        url = f"{self._base_url}{_CHAT_PATH}"
        try:
            async with self._http.stream("POST", url, json=payload, timeout=timeout_s) as response:
                self._raise_for_status(response)
                async for line in response.aiter_lines():
                    chunk = self._parse_sse_line(line)
                    if chunk is not None:
                        yield chunk
        except httpx.TimeoutException as exc:
            raise LlmTimeoutError(str(exc)) from exc
        except httpx.ConnectError as exc:
            raise LlmUnavailableError(str(exc)) from exc

    async def health(self) -> ModelHealth:
        model_name = next(iter(self._served_models), "")
        url = f"{self._base_url}{_MODELS_PATH}"
        try:
            response = await self._http.get(url, timeout=5.0)
        except (httpx.TimeoutException, httpx.TransportError):
            return ModelHealth(model_name=model_name, healthy=False)
        return ModelHealth(
            model_name=model_name,
            healthy=response.status_code == httpx.codes.OK,
        )

    # ---------- helpers internos ----------

    def _ensure_served(self, model: str) -> None:
        if not self.serves_model(model):
            raise ModelNotServedError(model)

    def _build_payload(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None,
        max_tokens: int,
        temperature: float,
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [self._encode_message(m) for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if tools:
            payload["tools"] = [self._encode_tool(t) for t in tools]
            payload["tool_choice"] = "auto"
        return payload

    @staticmethod
    def _encode_message(message: ChatMessage) -> dict[str, Any]:
        encoded: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.tool_call_id is not None:
            encoded["tool_call_id"] = message.tool_call_id
        if message.name is not None:
            encoded["name"] = message.name
        return encoded

    @staticmethod
    def _encode_tool(tool: ToolSpec) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    async def _post(self, payload: dict[str, Any], timeout_s: float) -> httpx.Response:
        url = f"{self._base_url}{_CHAT_PATH}"
        try:
            return await self._http.post(url, json=payload, timeout=timeout_s)
        except httpx.TimeoutException as exc:
            raise LlmTimeoutError(str(exc)) from exc
        except httpx.ConnectError as exc:
            raise LlmUnavailableError(str(exc)) from exc

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status = response.status_code
        if status < 400:
            return
        if status == httpx.codes.TOO_MANY_REQUESTS:
            raise LlmOverloadedError(f"HTTP {status}")
        if status in (httpx.codes.BAD_REQUEST, httpx.codes.UNPROCESSABLE_ENTITY):
            raise LlmBadRequestError(f"HTTP {status}")
        if status == httpx.codes.SERVICE_UNAVAILABLE:
            raise LlmUnavailableError(f"HTTP {status}")
        if status >= 500:
            raise LlmUnavailableError(f"HTTP {status}")
        raise LlmError(f"HTTP {status}")

    def _parse_completion(
        self, body: dict[str, Any], model: str, latency_ms: float
    ) -> CompletionResult:
        choices = body.get("choices") or []
        if not choices:
            raise LlmError("respuesta sin choices")
        choice = choices[0]
        message = choice.get("message") or {}
        usage = body.get("usage") or {}
        return CompletionResult(
            text=message.get("content") or "",
            tool_calls=self._parser.parse(message),
            finish_reason=choice.get("finish_reason") or "stop",
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            model_name=body.get("model") or model,
            latency_ms=latency_ms,
        )

    @staticmethod
    def _parse_sse_line(line: str) -> CompletionChunk | None:
        stripped = line.strip()
        if not stripped or not stripped.startswith("data:"):
            return None
        data = stripped[len("data:") :].strip()
        if not data or data == "[DONE]":
            return None
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            return None
        choices = event.get("choices") or []
        if not choices:
            return None
        choice = choices[0]
        delta = choice.get("delta") or {}
        return CompletionChunk(
            delta_text=delta.get("content") or "",
            tool_call_delta={"choices": [choice]} if delta.get("tool_calls") else None,
            finish_reason=choice.get("finish_reason"),
        )
