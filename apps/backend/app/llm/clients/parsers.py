"""Normalizador de tool calls en formato OpenAI (M2).

vLLM convierte el formato custom de cada modelo (``gemma4`` / ``hermes``)
a tool calls OpenAI estandar en el response HTTP. Por eso el backend
**siempre** ve ``tool_calls`` en formato OpenAI, sin importar el modelo, y
alcanza con UN solo normalizador en Python.

El mapping ``tool_parsers`` de ``ynara.config.json`` (``hermes`` /
``gemma4``) documenta que flag ``--tool-call-parser`` lanzar en el SERVER
vLLM (infra); **no se usa para parsear en Python**.

Shape OpenAI esperado en ``message.tool_calls[i]``::

    {"id": "call_x", "type": "function",
     "function": {"name": "calc", "arguments": "{\\"a\\": 1}"}}

``function.arguments`` es un *string* JSON; este parser lo convierte a dict.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from app.llm.errors import ToolParsingError
from app.llm.schemas import ToolCall


class OpenAIToolCallParser:
    """Implementa ``ToolCallParser`` para respuestas OpenAI de vLLM."""

    def parse(self, raw_message: dict[str, Any]) -> list[ToolCall]:
        """Normaliza ``message.tool_calls`` a una lista de ``ToolCall``.

        Lanza ``ToolParsingError`` si ``arguments`` no es JSON valido o si
        falta ``function.name``. No tumba el turno por si mismo: el caller
        decide que hacer.
        """
        raw_calls = raw_message.get("tool_calls")
        if not raw_calls:
            return []
        if not isinstance(raw_calls, list):
            raise ToolParsingError("tool_calls no es una lista")
        return [self._parse_one(call) for call in raw_calls]

    def accumulate(self, deltas: Iterable[dict[str, Any]]) -> list[ToolCall]:
        """Junta fragmentos de tool calls de un stream por ``index``.

        Cada delta OpenAI trae ``choices[0].delta.tool_calls[]`` con un
        ``index`` estable y fragmentos de ``id`` / ``function.name`` /
        ``function.arguments``. Acumulamos los fragmentos y parseamos el
        JSON de ``arguments`` recien al cerrar (``finish_reason ==
        "tool_calls"``); si el stream nunca cierra con tool_calls, igual
        devolvemos lo acumulado.
        """
        # index -> {"id": str, "name": str, "arguments": str}
        acc: dict[int, dict[str, str]] = {}
        for delta in deltas:
            for choice in self._choices(delta):
                inner = choice.get("delta")
                if not isinstance(inner, dict):
                    continue
                self._merge_tool_call_fragments(acc, inner.get("tool_calls"))
        return [self._finalize(acc[index]) for index in sorted(acc)]

    # ---------- helpers internos ----------

    def _parse_one(self, call: Any) -> ToolCall:
        if not isinstance(call, dict):
            raise ToolParsingError("tool call no es un objeto")
        function = call.get("function")
        if not isinstance(function, dict):
            raise ToolParsingError("falta el objeto function en la tool call")
        name = function.get("name")
        if not name or not isinstance(name, str):
            raise ToolParsingError("falta function.name en la tool call")
        arguments = self._decode_arguments(function.get("arguments"))
        call_id = call.get("id")
        return ToolCall(
            id=call_id if isinstance(call_id, str) and call_id else name,
            name=name,
            arguments=arguments,
        )

    @staticmethod
    def _decode_arguments(raw: Any) -> dict[str, Any]:
        # vLLM manda un string JSON; toleramos un dict ya parseado por
        # robustez, pero nada mas.
        if isinstance(raw, dict):
            return raw
        if raw is None or raw == "":
            return {}
        if not isinstance(raw, str):
            raise ToolParsingError("function.arguments no es un string JSON")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ToolParsingError("function.arguments no es JSON valido") from exc
        if not isinstance(parsed, dict):
            raise ToolParsingError("function.arguments no decodifica a objeto")
        return parsed

    @staticmethod
    def _choices(delta: dict[str, Any]) -> list[dict[str, Any]]:
        choices = delta.get("choices")
        if isinstance(choices, list):
            return [c for c in choices if isinstance(c, dict)]
        return []

    @staticmethod
    def _merge_tool_call_fragments(acc: dict[int, dict[str, str]], fragments: Any) -> None:
        if not isinstance(fragments, list):
            return
        for fragment in fragments:
            if not isinstance(fragment, dict):
                continue
            index = fragment.get("index", 0)
            if not isinstance(index, int):
                continue
            slot = acc.setdefault(index, {"id": "", "name": "", "arguments": ""})
            frag_id = fragment.get("id")
            if isinstance(frag_id, str):
                slot["id"] += frag_id
            function = fragment.get("function")
            if isinstance(function, dict):
                name = function.get("name")
                if isinstance(name, str):
                    slot["name"] += name
                args = function.get("arguments")
                if isinstance(args, str):
                    slot["arguments"] += args

    def _finalize(self, slot: dict[str, str]) -> ToolCall:
        name = slot["name"]
        if not name:
            raise ToolParsingError("falta function.name al cerrar el stream")
        arguments = self._decode_arguments(slot["arguments"] or "{}")
        return ToolCall(
            id=slot["id"] or name,
            name=name,
            arguments=arguments,
        )
