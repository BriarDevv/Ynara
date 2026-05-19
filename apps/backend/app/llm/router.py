"""Router LLM: decide modelo y construye la llamada según el modo.

Decisión: el modelo a usar viene de ``ynara.config.json[modes][...].model``.
Este archivo NO duplica esa configuración: la carga en runtime.

Reglas:
- Gemma solo lee memoria.
- Qwen lee y escribe memoria, puede llamar tools.
- El router nunca acepta inputs sin sanear; valida modo antes de
  rutear.

TODO: la implementación real (clientes HTTP a vLLM, manejo de stream,
parseo de tool calls) se cierra en un PR posterior. Esto es el
esqueleto.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.enums import Mode


class ChatRequest(BaseModel):
    text: str
    mode: Mode
    session_id: str | None = None


class ChatResponse(BaseModel):
    text: str
    actions: list[dict[str, Any]] = []
    session_id: str


async def route(request: ChatRequest) -> ChatResponse:
    """Punto de entrada único al LLM.

    TODO: implementar.
    - Cargar configuración del modo desde ``ynara.config.json``.
    - Resolver embeddings de la query si hace falta.
    - Recuperar contexto de memoria (según ``memory_layers`` del modo).
    - Llamar al modelo (Gemma o Qwen) con prompt + contexto + tools.
    - Si es Qwen y devolvió tool calls: ejecutar, alimentar, repetir.
    - Encolar consolidación de memoria asíncrona (Celery).
    - Devolver respuesta al cliente.
    """
    raise NotImplementedError("router.route TODO")
