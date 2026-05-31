"""Motor de extraccion de memoria semantica + procedural (M8 Ola 2).

NO es un store (no toca SQL ni las tablas sagradas directamente).
Es la inteligencia que LLAMA a los stores: extrae ops del turno del
usuario/modelo y las aplica via ``SemanticMemoryStore`` /
``ProceduralMemoryStore``.

Componentes:
- ``MemoryOp``: op atómica que describe qué escribir/borrar.
- ``MemoryEngine`` (Protocol): contrato de extraccion.
- ``QwenMemoryEngine``: implementacion real via Qwen (LLM call + parseo
  defensivo).
- ``FakeMemoryEngine``: implementacion para tests (sin LLM).
- ``apply_ops()``: aplica una lista de ``MemoryOp`` contra los stores.

Decisiones (ADR-010 + critica adversarial M8, NO re-litigar):
1. Solo Qwen escribe. ``route()`` solo encola si ``model_cfg.writes_memory``.
2. NUNCA source_session_id: el session_id de Ola 2 es OPACO.
3. NUNCA episodica: layer = 'semantic' | 'procedural' solamente.
4. Parseo defensivo: JSON invalido -> [] sin crashear el worker.
5. Sin dedup search-based en Ola 2: ops directo sin search-before-add.
   (gateado por embedder/reranker real; FakeReranker no modela similitud).
6. Ningun dato de usuario a logs (regla #4).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from app.llm.clients.base import LLMClient
from app.llm.schemas import ChatMessage
from app.schemas.memory import ProceduralMemoryUpsert, SemanticMemoryCreate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MemoryOp — op atómica de escritura/borrado
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemoryOp:
    """Operacion atomica de consolidacion de memoria.

    Campos:
        op: ADD | UPDATE | DELETE | NOOP.
        layer: 'semantic' (hechos) o 'procedural' (preferencias estructuradas).
        content: Texto del hecho (ADD/UPDATE semantic).
        key: Clave de la entrada procedural (ADD/UPDATE/DELETE procedural).
        value: Dict de la preferencia (ADD/UPDATE procedural).
        target_id: UUID como str del registro a actualizar/borrar (UPDATE/DELETE
            semantic).
    """

    op: Literal["ADD", "UPDATE", "DELETE", "NOOP"]
    layer: Literal["semantic", "procedural"]
    content: str = ""
    key: str | None = None
    value: dict[str, Any] | None = field(default=None)
    target_id: str | None = None


# ---------------------------------------------------------------------------
# MemoryEngine — Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class MemoryEngine(Protocol):
    """Contrato de extraccion de operaciones de memoria a partir de un turno."""

    async def consolidate(
        self,
        *,
        user_msg: str,
        model_response: str,
        mode: str,
    ) -> list[MemoryOp]:
        """Extrae ops de memoria del turno (user_msg + model_response).

        Args:
            user_msg: Mensaje del usuario (plaintext, no loguear).
            model_response: Respuesta del modelo (plaintext, no loguear).
            mode: Modo activo de la sesion (p.ej. 'vida', 'estudio').

        Returns:
            Lista de ``MemoryOp`` a aplicar. Vacia si no hay nada que guardar.
        """
        ...


# ---------------------------------------------------------------------------
# Prompt de extraccion
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM = """\
Sos un extractor de memoria para un asistente personal llamado Ynara.
Tu unica tarea es analizar un turno de conversacion (mensaje del usuario + \
respuesta del asistente) y devolver una lista JSON de operaciones de memoria.

REGLAS ESTRICTAS:
1. Solo extrae capas "semantic" y "procedural". NUNCA episodica.
2. "semantic": hechos concretos y duraderos sobre el usuario (nombre, edad, \
trabajo, relaciones, objetivos, eventos importantes). Un hecho por op.
3. "procedural": preferencias o patrones de comportamiento estructurados \
(idioma preferido, estilo de respuesta, configuraciones, habitos). \
Usa key descriptiva en snake_case y value como dict con los atributos.
4. NO inventes informacion que no este en el turno. Si no hay nada relevante, \
devuelve [{"op":"NOOP","layer":"semantic"}].
5. Usa ADD para hechos/preferencias nuevos. UPDATE para corregir/refinar algo \
existente (requiere target_id para semantic). DELETE para eliminar algo \
invalidado (requiere target_id para semantic o key para procedural).
6. Para ADD semantic: incluye "content" con el hecho en primera persona del \
asistente (p.ej. "El usuario se llama Carlos").
7. Para ADD/UPDATE procedural: "key" en snake_case, "value" como dict.
8. NO incluyas datos medicos sensibles sin consentimiento explicito del usuario.

FORMATO DE SALIDA (SOLO JSON, sin texto extra, sin markdown):
[
  {"op": "ADD", "layer": "semantic", "content": "El usuario trabaja como \
medico pediatra."},
  {"op": "ADD", "layer": "procedural", "key": "idioma_preferido", \
"value": {"idioma": "es-AR", "tono": "informal"}},
  {"op": "NOOP", "layer": "semantic"}
]

Campos validos por op:
- ADD semantic: op, layer, content
- ADD procedural: op, layer, key, value
- UPDATE semantic: op, layer, content, target_id (UUID del hecho a reemplazar)
- UPDATE procedural: op, layer, key, value
- DELETE semantic: op, layer, target_id
- DELETE procedural: op, layer, key
- NOOP: op, layer
"""

_EXTRACTION_USER_TMPL = """\
[MODO: {mode}]

[MENSAJE DEL USUARIO]
{user_msg}

[RESPUESTA DEL ASISTENTE]
{model_response}

Devuelve SOLO la lista JSON de operaciones de memoria. Nada mas."""


# ---------------------------------------------------------------------------
# QwenMemoryEngine
# ---------------------------------------------------------------------------

_VALID_OPS: frozenset[str] = frozenset({"ADD", "UPDATE", "DELETE", "NOOP"})
_VALID_LAYERS: frozenset[str] = frozenset({"semantic", "procedural"})


def _parse_ops(raw_text: str) -> list[MemoryOp]:
    """Parseo defensivo del JSON de ops devuelto por Qwen.

    Regla #6 (critica adversarial M8): si el parse falla o el resultado
    no es lista, devuelve [] sin propagar. El worker jamas debe caerse
    por un JSON malo de Qwen.
    """
    try:
        data = json.loads(raw_text.strip())
    except (json.JSONDecodeError, ValueError):
        logger.debug("memory_engine: JSON invalido en respuesta de Qwen (descartado)")
        return []

    if not isinstance(data, list):
        logger.debug("memory_engine: respuesta de Qwen no es lista (descartado)")
        return []

    ops: list[MemoryOp] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        op_val = item.get("op", "")
        layer_val = item.get("layer", "")
        if op_val not in _VALID_OPS or layer_val not in _VALID_LAYERS:
            continue
        if op_val == "NOOP":
            ops.append(MemoryOp(op="NOOP", layer=layer_val))  # type: ignore[arg-type]
            continue
        try:
            ops.append(
                MemoryOp(
                    op=op_val,  # type: ignore[arg-type]
                    layer=layer_val,  # type: ignore[arg-type]
                    content=str(item.get("content", "")),
                    key=item.get("key") or None,
                    value=item.get("value") if isinstance(item.get("value"), dict) else None,
                    target_id=item.get("target_id") or None,
                )
            )
        except (TypeError, ValueError):
            # Op malformada: skip sin crashear.
            continue

    return ops


class QwenMemoryEngine:
    """Extractor de memoria usando Qwen via ``LLMClient``.

    Llama al modelo con un prompt de extraccion y parsea la respuesta JSON
    de forma defensiva (decision #6 M8): nunca propaga errores de parseo.
    """

    def __init__(self, llm_client: LLMClient, served_name: str = "qwen") -> None:
        self._client = llm_client
        self._served_name = served_name

    async def consolidate(
        self,
        *,
        user_msg: str,
        model_response: str,
        mode: str,
    ) -> list[MemoryOp]:
        """Extrae ops de memoria del turno via Qwen.

        El contenido del turno NO se loguea (regla #4: ningun dato de
        usuario a logs). Si el LLM falla o devuelve JSON invalido,
        devuelve [] sin propagar.
        """
        user_content = _EXTRACTION_USER_TMPL.format(
            mode=mode,
            user_msg=user_msg,
            model_response=model_response,
        )
        messages = [
            ChatMessage(role="system", content=_EXTRACTION_SYSTEM),
            ChatMessage(role="user", content=user_content),
        ]
        try:
            result = await self._client.complete(
                model=self._served_name,
                messages=messages,
                temperature=0.1,  # baja temperatura para extraccion estructurada
                max_tokens=512,
            )
        except Exception:
            # El worker nunca debe caerse por un fallo del LLM en la extraccion.
            logger.debug("memory_engine: fallo al llamar a Qwen para extraccion (descartado)")
            return []

        return _parse_ops(result.text)


# ---------------------------------------------------------------------------
# FakeMemoryEngine
# ---------------------------------------------------------------------------


class FakeMemoryEngine:
    """Implementacion para tests: devuelve ops prefijadas sin llamar al LLM."""

    def __init__(self, ops: list[MemoryOp]) -> None:
        self._ops = list(ops)
        self.consolidate_calls: list[dict[str, str]] = []

    async def consolidate(
        self,
        *,
        user_msg: str,
        model_response: str,
        mode: str,
    ) -> list[MemoryOp]:
        self.consolidate_calls.append(
            {"user_msg": user_msg, "model_response": model_response, "mode": mode}
        )
        return list(self._ops)


# ---------------------------------------------------------------------------
# apply_ops — aplica ops contra los stores reales
# ---------------------------------------------------------------------------


async def apply_ops(
    ops: list[MemoryOp],
    *,
    semantic_store: Any,
    procedural_store: Any,
) -> int:
    """Aplica cada op contra los stores de memoria.

    Reglas de aplicacion (decision #5 M8 — sin dedup search-based):
    - ADD semantic    -> semantic_store.add(SemanticMemoryCreate(content=...))
    - ADD/UPDATE proc -> procedural_store.upsert(ProceduralMemoryUpsert(key, value))
    - UPDATE semantic -> semantic_store.update(UUID(target_id), content)
    - DELETE semantic -> semantic_store.delete(UUID(target_id))
    - DELETE proc     -> procedural_store.delete(key)
    - NOOP            -> skip

    Robustez: si target_id/key faltan para una op que los requiere, la op
    se skippea silenciosamente. Nunca propaga errores individuales de ops
    (regla: el worker no muere por una op mala).

    NOTA: sin dedup search-based en Ola 2. El search-before-add para evitar
    duplicados semanticos queda gateado por el embedder/reranker real
    (FakeReranker no modela similitud). Se implementa en Ola 3+.

    Args:
        ops: Lista de ``MemoryOp`` a aplicar.
        semantic_store: Instancia de ``SemanticMemoryStore`` del usuario.
        procedural_store: Instancia de ``ProceduralMemoryStore`` del usuario.

    Returns:
        Cantidad de ops efectivamente aplicadas (NOOP y skips no cuentan).
    """
    applied = 0
    for op in ops:
        try:
            if op.op == "NOOP":
                continue

            if op.layer == "semantic":
                if op.op == "ADD":
                    if not op.content:
                        continue
                    await semantic_store.add(
                        SemanticMemoryCreate(content=op.content)
                    )
                    applied += 1

                elif op.op == "UPDATE":
                    if not op.target_id or not op.content:
                        continue
                    result = await semantic_store.update(UUID(op.target_id), op.content)
                    if result is not None:
                        applied += 1

                elif op.op == "DELETE":
                    if not op.target_id:
                        continue
                    deleted = await semantic_store.delete(UUID(op.target_id))
                    if deleted:
                        applied += 1

            elif op.layer == "procedural":
                if op.op in ("ADD", "UPDATE"):
                    if not op.key or op.value is None:
                        continue
                    await procedural_store.upsert(
                        ProceduralMemoryUpsert(key=op.key, value=op.value)
                    )
                    applied += 1

                elif op.op == "DELETE":
                    if not op.key:
                        continue
                    deleted = await procedural_store.delete(op.key)
                    if deleted:
                        applied += 1

        except Exception:
            # Op individual falla: loguear (sin contenido) y seguir.
            logger.debug(
                "memory_engine: op %s/%s fallida, skip", op.op, op.layer
            )
            continue

    return applied
