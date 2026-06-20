"""Cliente HTTP contra un endpoint OpenAI-compatible (vLLM o Ollama,
ADR-014 D1/D2). En 16GB apunta a Ollama; en 24GB+ a vLLM.

``VllmClient`` habla el endpoint ``/v1/chat/completions`` de un unico
proceso de serving (un modelo por proceso vLLM, ADR-009 D1; Ollama puede
servir varios modelos por endpoint). Recibe el ``httpx.AsyncClient`` por
constructor, asi que es testeable con ``httpx.MockTransport`` sin red real.
Nunca importa FastAPI ni vLLM.

Mapeo de errores HTTP a la taxonomia (``app/llm/errors.py``):

- timeout            -> ``LlmTimeoutError``
- ConnectError       -> ``LlmUnavailableError``
- 429                -> ``LlmOverloadedError``
- 400 / 422          -> ``LlmBadRequestError``
- 400 con firma de overflow en el body -> ``LlmContextOverflowError``
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
    LlmContextOverflowError,
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

# Esfuerzo de razonamiento para thinking=True (param OpenAI-standard
# ``reasoning_effort``). "none" desactiva el thinking; "medium" es un default
# balanceado para el rol agente. Tuneable a "low"/"high"/"max" si hiciera falta.
_THINKING_ON_EFFORT = "medium"

# Firmas de overflow de contexto en el body de un 400 de vLLM. vLLM (y el
# server OpenAI-compatible) devuelven un 400 plano cuando el prompt + la
# generacion exceden la ventana; el body trae una de estas frases. Se matchea
# en minuscula contra el texto del body para mapear a LlmContextOverflowError
# (subclase de LlmBadRequestError) en vez del 400 generico. Regla #4: NUNCA se
# propaga el body crudo; solo se usa para decidir el TIPO de excepcion, cuyo
# detail es una etiqueta fija.
_CONTEXT_OVERFLOW_SIGNATURES: tuple[str, ...] = (
    "maximum context length",
    "context length",
    "reduce the length of the messages",
)


def _is_context_overflow(body_text: str | None) -> bool:
    """``True`` si el body de un 400 trae una firma de overflow de contexto.

    Match case-insensitive contra ``_CONTEXT_OVERFLOW_SIGNATURES``. El body NO
    se loguea ni se propaga: solo se inspecciona para elegir el TIPO de
    excepcion (regla #4).
    """
    if not body_text:
        return False
    lowered = body_text.lower()
    return any(sig in lowered for sig in _CONTEXT_OVERFLOW_SIGNATURES)


class VllmClient:
    """Implementa ``LLMClient`` contra un proceso vLLM."""

    def __init__(
        self,
        *,
        base_url: str,
        served_models: frozenset[str],
        http_client: httpx.AsyncClient,
        parser: ToolCallParser,
        default_timeout_s: float = 30.0,
    ) -> None:
        """Un ``VllmClient`` = un proceso vLLM.

        ``served_models`` normalmente tiene un solo ``served_name``: vLLM
        sirve un modelo por proceso (ADR-009 D1). Se modela como
        ``frozenset`` para que el pool rutee con ``serves_model()`` de
        forma uniforme; ``health()`` reporta un served_name de forma
        determinista.

        ``default_timeout_s`` es el timeout por request cuando el caller no
        pasa uno explicito; el router (M8) construye el cliente con
        ``config.serving.request_timeout_s`` (ver ynara.config.json).
        """
        self._base_url = base_url.rstrip("/")
        self._served_models = served_models
        self._http = http_client
        self._parser = parser
        self._default_timeout_s = default_timeout_s

    def serves_model(self, model: str) -> bool:
        return model in self._served_models

    async def aclose(self) -> None:
        """Cierra el ``httpx.AsyncClient`` subyacente (libera el connection pool).

        Lo llama el teardown del pool/lifespan al apagar la app. El cliente HTTP
        se construye afuera (la factory) y se le cede a este ``VllmClient``, que
        queda como su owner para el cierre — sin esto se filtran sockets en prod.
        """
        await self._http.aclose()

    async def complete(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        thinking: bool | None = None,
        timeout_s: float | None = None,
    ) -> CompletionResult:
        self._ensure_served(model)
        payload = self._build_payload(
            model=model,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
            thinking=thinking,
            stream=False,
        )
        started = time.perf_counter()
        response = await self._post(payload, self._resolve_timeout(timeout_s))
        latency_ms = (time.perf_counter() - started) * 1000.0
        # En no-streaming la response ya esta leida: pasamos el body para que
        # un 400 de overflow se mapee a LlmContextOverflowError (P2.4).
        self._raise_for_status(response, body_text=response.text)
        return self._parse_completion(response.json(), model, latency_ms)

    async def stream(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        thinking: bool | None = None,
        timeout_s: float | None = None,
    ) -> AsyncIterator[CompletionChunk]:
        self._ensure_served(model)
        payload = self._build_payload(
            model=model,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
            thinking=thinking,
            stream=True,
        )
        url = f"{self._base_url}{_CHAT_PATH}"
        effective_timeout = self._resolve_timeout(timeout_s)
        try:
            async with self._http.stream(
                "POST", url, json=payload, timeout=effective_timeout
            ) as response:
                self._raise_for_status(response)
                async for line in response.aiter_lines():
                    chunk = self._parse_sse_line(line)
                    if chunk is not None:
                        yield chunk
        except httpx.TimeoutException as exc:
            raise LlmTimeoutError("timeout HTTP") from exc
        except httpx.ConnectError as exc:
            raise LlmUnavailableError("connect error") from exc

    async def health(self) -> ModelHealth:
        # ``min`` da un nombre estable aunque el set tuviera >1 (ver __init__).
        model_name = min(self._served_models, default="")
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

    def _resolve_timeout(self, timeout_s: float | None) -> float:
        """Timeout por request: el explicito del caller o el default del cliente.

        El router (M8) construye el cliente con
        ``default_timeout_s=config.serving.request_timeout_s``; cada llamada
        puede hacer un override puntual con ``timeout_s``.
        """
        return timeout_s if timeout_s is not None else self._default_timeout_s

    def _build_payload(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None,
        max_tokens: int,
        temperature: float,
        thinking: bool | None,
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
        # Control del modo de razonamiento por request (ADR-012 D4). Solo se emite
        # si el caller decide (True/False); con ``None`` no se agrega nada y se
        # preserva el default del server (comportamiento previo exacto). Se emiten
        # DOS params por compatibilidad de motor (ADR-014: 16GB=Ollama, 24GB+=vLLM):
        #  - ``reasoning_effort`` (OpenAI-standard): el UNICO que honra el endpoint
        #    OpenAI-compatible de Ollama ("none"=OFF, "medium"=ON); vLLM tambien lo
        #    soporta. Verificado contra Ollama real: ignora chat_template_kwargs y
        #    suprime el thinking solo con reasoning_effort.
        #  - ``chat_template_kwargs.enable_thinking`` (vLLM-native): cubre vLLM sin
        #    reasoning-parser, donde el flag va directo al chat template.
        # Regla #4 intacta: esto solo gobierna el modo de razonamiento on-prem.
        if thinking is not None:
            payload["reasoning_effort"] = _THINKING_ON_EFFORT if thinking else "none"
            payload["chat_template_kwargs"] = {"enable_thinking": thinking}
        return payload

    @staticmethod
    def _encode_message(message: ChatMessage) -> dict[str, Any]:
        encoded: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.tool_call_id is not None:
            encoded["tool_call_id"] = message.tool_call_id
        if message.name is not None:
            encoded["name"] = message.name
        # Re-serializar las tool_calls del assistant al wire OpenAI (multi-turno con
        # tool): sin esto el server (Ollama en 16GB / vLLM en 24GB+, ADR-014) recibe un
        # assistant con ``content:null`` y SIN tool_calls -> 400 ("invalid message
        # content type: <nil>"), el tool loop nunca cierra y el turno DEGRADA (con la
        # consolidacion de memoria sin correr, porque un turno degradado no encola). El
        # ``arguments`` viaja como JSON string (formato wire OpenAI), a diferencia del
        # ``ToolCall.arguments`` de dominio que ya viene parseado a dict. Truthy check (no
        # ``is not None``) a proposito: una lista vacia ``[]`` NO debe emitir
        # ``"tool_calls": []`` (un assistant con ``content:null`` + tool_calls vacio seria
        # tan invalido como sin la clave); solo se serializa si hay calls reales.
        if message.tool_calls:
            encoded["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in message.tool_calls
            ]
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
            raise LlmTimeoutError("timeout HTTP") from exc
        except httpx.ConnectError as exc:
            raise LlmUnavailableError("connect error") from exc

    @staticmethod
    def _raise_for_status(response: httpx.Response, *, body_text: str | None = None) -> None:
        status = response.status_code
        if status < 400:
            return
        if status == httpx.codes.TOO_MANY_REQUESTS:
            raise LlmOverloadedError(f"HTTP {status}")
        if status in (httpx.codes.BAD_REQUEST, httpx.codes.UNPROCESSABLE_ENTITY):
            # Un 400 cuyo body trae la firma de overflow es contexto excedido
            # (subclase permanente especifica); el resto es un 400 generico.
            # Regla #4: el detail es una etiqueta fija, nunca el body crudo.
            if status == httpx.codes.BAD_REQUEST and _is_context_overflow(body_text):
                raise LlmContextOverflowError(f"HTTP {status}")
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
            # Canal de razonamiento separado (qwen via Ollama lo manda en
            # ``message.reasoning``, no inline en ``content``).
            reasoning=message.get("reasoning") or None,
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
            # Delta del canal de razonamiento (qwen via Ollama: ``delta.reasoning``,
            # APARTE del ``content`` que queda vacio durante el thinking).
            reasoning_delta=delta.get("reasoning") or None,
        )
