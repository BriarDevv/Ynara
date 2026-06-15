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
2. source_session_id (provenance, M10 Ola 1): ``apply_ops`` recibe el
   ``source_session_id`` (UUID de la ``ChatSession``) y lo persiste SOLO en el
   ADD semantic (no en UPDATE/DELETE). Es FK opcional a ``sessions.id``.
3. NUNCA episodica: layer = 'semantic' | 'procedural' solamente.
4. Parseo defensivo: JSON invalido -> [] sin crashear el worker.
5. Sin dedup search-based en Ola 2: ops directo sin search-before-add.
   (gateado por embedder/reranker real; FakeReranker no modela similitud).
6. Ningun dato de usuario a logs (regla #4).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.llm.clients.base import LLMClient
from app.llm.schemas import ChatMessage
from app.memory.hashing import compute_record_hash, procedural_hash_payload
from app.schemas.memory import ProceduralMemoryUpsert, SemanticMemoryCreate

if TYPE_CHECKING:
    from app.memory.audit import AuditStore

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


@dataclass(frozen=True)
class SessionSummary:
    """Resumen episodico de una sesion completa (output de ``summarize``).

    Campos:
        summary: Parrafo en tercera persona con lo que paso en la sesion. Vacio
            ("") cuando el LLM no devolvio un resumen utilizable (parseo
            defensivo): el caller (worker episodico) NO debe persistir un
            episodio con summary vacio.
        topics: Metadata estructurada de la sesion (temas, tono, etc.). Dict
            vacio cuando no hay metadata.
    """

    summary: str = ""
    topics: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# MemoryEngine — Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class MemoryEngine(Protocol):
    """Contrato del motor de memoria: extracción de ops por turno + resumen de sesión."""

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

    async def summarize(self, *, transcript: str, mode: str) -> SessionSummary:
        """Resume un transcript de sesión completo a un ``SessionSummary``.

        Lo usa el worker episódico (``consolidate_session``) al cerrar la sesión.
        El transcript NO se loguea (regla #4). Ante un fallo del LLM o JSON
        inválido devuelve un ``SessionSummary`` vacío (``summary=""``) sin
        propagar: el caller NO crea el episodio cuando el summary es vacío.
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
# Prompt de resumen episodico
# ---------------------------------------------------------------------------

_SUMMARY_SYSTEM = """\
Sos un resumidor de conversaciones para un asistente personal llamado Ynara.
Tu unica tarea es leer el transcript de una sesion completa (turnos del usuario y \
del asistente) y devolver un objeto JSON con un resumen episodico de la sesion.

REGLAS ESTRICTAS:
1. El "summary" es un parrafo en tercera persona que captura lo que paso en la \
sesion: de que se hablo, que pidio el usuario, que se resolvio. Conciso pero \
completo (2 a 5 oraciones).
2. "topics" es un objeto con metadata estructurada de la sesion (p.ej. \
{"temas": ["trabajo", "salud"], "tono": "reflexivo"}). Puede ir vacio ({}).
3. NO inventes informacion que no este en el transcript.
4. NO incluyas datos sensibles innecesarios; resumi a nivel de tema, no de detalle \
intimo, salvo que sea central a la sesion.

FORMATO DE SALIDA (SOLO JSON, sin texto extra, sin markdown):
{"summary": "El usuario hablo de ...", "topics": {"temas": ["..."]}}
"""

_SUMMARY_USER_TMPL = """\
[MODO: {mode}]

[TRANSCRIPT DE LA SESION]
{transcript}

Devuelve SOLO el objeto JSON con "summary" y "topics". Nada mas."""


# ---------------------------------------------------------------------------
# QwenMemoryEngine
# ---------------------------------------------------------------------------

_VALID_OPS: frozenset[str] = frozenset({"ADD", "UPDATE", "DELETE", "NOOP"})
_VALID_LAYERS: frozenset[str] = frozenset({"semantic", "procedural"})

# Qwen es un modelo *thinking*. consolidate/summarize fuerzan thinking=False
# (output JSON limpio, ADR-012 D4), pero si el server igual antepone un bloque
# <think>...</think> (default del server / Ollama sin reasoning-parser) o envuelve
# el JSON en un fence markdown, se limpia ANTES de json.loads para no degradar la
# extraccion a [] / summary vacio en silencio (#235).
_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_reasoning_and_fences(raw_text: str) -> str:
    """Quita bloques ``<think>...</think>`` y fences markdown del texto del LLM.

    Defensa en profundidad del parseo (Qwen es thinking model): aunque
    ``consolidate``/``summarize`` mandan ``thinking=False``, esto tolera que el
    server emita razonamiento igual o devuelva el JSON dentro de un fence
    ```` ```json ... ``` ````.
    """
    cleaned = _THINK_BLOCK_RE.sub("", raw_text).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    return cleaned.strip()


def _parse_ops(raw_text: str) -> list[MemoryOp]:
    """Parseo defensivo del JSON de ops devuelto por Qwen.

    Regla #6 (critica adversarial M8): si el parse falla o el resultado
    no es lista, devuelve [] sin propagar. El worker jamas debe caerse
    por un JSON malo de Qwen.
    """
    try:
        data = json.loads(_strip_reasoning_and_fences(raw_text))
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


def _parse_summary(raw_text: str) -> SessionSummary:
    """Parseo defensivo del JSON de resumen episodico devuelto por Qwen.

    Espejo de ``_parse_ops`` (regla #6): si el parse falla, el resultado no es un
    objeto, o ``summary`` no es un str no-vacio, devuelve un ``SessionSummary``
    vacio (``summary=""``) sin propagar. El worker episodico jamas debe caerse por
    un JSON malo de Qwen; con ``summary=""`` el caller decide no crear el episodio.
    """
    try:
        data = json.loads(_strip_reasoning_and_fences(raw_text))
    except (json.JSONDecodeError, ValueError):
        logger.debug("memory_engine: JSON invalido en resumen de Qwen (descartado)")
        return SessionSummary()

    if not isinstance(data, dict):
        logger.debug("memory_engine: resumen de Qwen no es objeto (descartado)")
        return SessionSummary()

    summary = data.get("summary", "")
    if not isinstance(summary, str) or not summary.strip():
        logger.debug("memory_engine: resumen de Qwen sin 'summary' valido (descartado)")
        return SessionSummary()

    topics = data.get("topics", {})
    if not isinstance(topics, dict):
        topics = {}

    return SessionSummary(summary=summary.strip(), topics=topics)


class QwenMemoryEngine:
    """Extractor de memoria usando Qwen via ``LLMClient``.

    Llama al modelo con un prompt de extraccion y parsea la respuesta JSON
    de forma defensiva (decision #6 M8): nunca propaga errores de parseo.
    Fuerza ``thinking=False`` en ambas llamadas (ADR-012 D4): la extraccion y el
    resumen necesitan JSON puro, y el razonamiento de Qwen (thinking model)
    contaminaria ``result.text`` y degradaria el parseo en silencio (#235).
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
                # thinking OFF (ADR-012 D4): la extraccion quiere JSON puro. Qwen es
                # thinking model y su razonamiento contaminaria result.text y rompria
                # el parseo (-> [] mudo). El default del server no es confiable aca.
                thinking=False,
                max_tokens=512,
            )
        except Exception:
            # El worker nunca debe caerse por un fallo del LLM en la extraccion.
            logger.debug("memory_engine: fallo al llamar a Qwen para extraccion (descartado)")
            return []

        return _parse_ops(result.text)

    async def summarize(self, *, transcript: str, mode: str) -> SessionSummary:
        """Resume un transcript de sesion completo a un ``SessionSummary`` via Qwen.

        Lo usa el worker episodico (``consolidate_session``) al cerrar la sesion:
        recibe el transcript reconstruido de los turnos descifrados y devuelve el
        ``summary`` (a cifrar + embeddear en ``episodic_memory``) + ``topics``.

        El contenido del transcript NO se loguea (regla #4: ningun dato de usuario
        a logs). Si el LLM falla o devuelve JSON invalido, devuelve un
        ``SessionSummary`` vacio (``summary=""``) sin propagar: el caller NO crea
        el episodio cuando el summary es vacio.
        """
        user_content = _SUMMARY_USER_TMPL.format(mode=mode, transcript=transcript)
        messages = [
            ChatMessage(role="system", content=_SUMMARY_SYSTEM),
            ChatMessage(role="user", content=user_content),
        ]
        try:
            result = await self._client.complete(
                model=self._served_name,
                messages=messages,
                temperature=0.2,  # baja temperatura para un resumen estable
                # thinking OFF (ADR-012 D4): el resumen quiere JSON puro; el <think>
                # de Qwen romperia el parseo (-> summary vacio mudo).
                thinking=False,
                max_tokens=512,
            )
        except Exception:
            # El worker nunca debe caerse por un fallo del LLM en el resumen.
            logger.debug("memory_engine: fallo al llamar a Qwen para resumen (descartado)")
            return SessionSummary()

        return _parse_summary(result.text)


# ---------------------------------------------------------------------------
# FakeMemoryEngine
# ---------------------------------------------------------------------------


class FakeMemoryEngine:
    """Implementacion para tests: ops + summary prefijados, sin llamar al LLM."""

    def __init__(self, ops: list[MemoryOp], *, summary: SessionSummary | None = None) -> None:
        self._ops = list(ops)
        self._summary = summary if summary is not None else SessionSummary()
        self.consolidate_calls: list[dict[str, str]] = []
        self.summarize_calls: list[dict[str, str]] = []

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

    async def summarize(self, *, transcript: str, mode: str) -> SessionSummary:
        self.summarize_calls.append({"transcript": transcript, "mode": mode})
        return self._summary


# ---------------------------------------------------------------------------
# apply_ops — aplica ops contra los stores reales
# ---------------------------------------------------------------------------


async def apply_ops(
    ops: list[MemoryOp],
    *,
    session: AsyncSession | None = None,
    semantic_store: Any,
    procedural_store: Any,
    source_session_id: UUID | None = None,
    audit_store: AuditStore | None = None,
    origin_model: LlmModel | None = None,
    origin_mode: Mode | None = None,
) -> int:
    """Aplica cada op contra los stores de memoria.

    Reglas de aplicacion (decision #5 M8 — sin dedup search-based):
    - ADD semantic    -> semantic_store.add(SemanticMemoryCreate(content=...,
      source_session_id=...))
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

    PROVENANCE (M10 Ola 1): ``source_session_id`` se setea SOLO en el branch
    ADD semantic (alta de un hecho nuevo). NO se propaga a UPDATE ni a DELETE:
    un UPDATE refina el texto del hecho pero NO cambia de que sesion vino el
    hecho original (su provenance se decidio cuando se hizo el ADD), y un DELETE
    lo borra. Es FK opcional a ``sessions.id`` (``ondelete=SET NULL``): si la
    ``ChatSession`` se borra, el hecho sobrevive con ``source_session_id`` NULL.

    AUDIT (issue #158): si ``audit_store`` no es ``None``, tras CADA op
    EFECTIVAMENTE aplicada se escribe una fila de ``audit_log`` con la metadata
    de la operacion (``operation`` / ``target_layer`` / ``target_id`` /
    ``origin_*``) + un ``record_hash`` sha256. REGLA #4: el ``record_hash`` es el
    sha256 hex (64 chars) del contenido/identificador afectado, NUNCA el
    contenido en claro — cero PII a la tabla de auditoria. ``apply_ops`` NUNCA
    toca episodica (donde vive lo sensible), asi que ``sensitive=False`` siempre.
    NOOP y ops skippeadas (target_id/key faltante, update/delete sin match) NO se
    auditan: solo se audita lo que de verdad cambio el estado de la memoria.

    ATOMICIDAD POR-OP (savepoint): cuando ``session`` se pasa (path real), cada op
    + su fila de audit corren en un ``begin_nested()`` (SAVEPOINT). Asi la op de
    memoria y su auditoria son ATOMICAS (las dos o ninguna) y, sobre todo, un fallo
    NO envenena la transaccion: en Postgres un statement que falla aborta la tx
    entera, asi que sin el savepoint el ``except`` por-op daria FALSA sensacion de
    aislamiento (las ops siguientes fallarian con ``PendingRollbackError`` y el
    ``commit`` final tumbaria el worker). El savepoint acota el rollback a esa sola
    op; ``applied`` cuenta solo las que confirmaron. Con ``session=None`` (unit
    tests con stores fake, sin transaccion real) se corre sin savepoint.

    Args:
        ops: Lista de ``MemoryOp`` a aplicar.
        session: ``AsyncSession`` compartida por los stores, para el savepoint
            por-op (``begin_nested``). ``None`` (default) = sin savepoint
            (back-compat con los unit tests de stores fake).
        semantic_store: Instancia de ``SemanticMemoryStore`` del usuario.
        procedural_store: Instancia de ``ProceduralMemoryStore`` del usuario.
        source_session_id: UUID de la ``ChatSession`` que origino el turno, o
            ``None`` si no se pudo determinar. Se persiste SOLO en ADD semantic
            como provenance del hecho (M10 Ola 1).
        audit_store: ``AuditStore`` del usuario (misma sesion que los stores de
            memoria) o ``None``. Si es ``None``, no se escribe auditoria (back-compat
            con los tests/callers que no la pasan).
        origin_model: Modelo LLM que origino la consolidacion (``LlmModel.QWEN`` en
            el path real). Se persiste como ``origin_model`` en cada fila de audit.
        origin_mode: Modo activo de la sesion, ya parseado a ``Mode`` (o ``None`` si
            el modo era invalido). Se persiste como ``origin_mode`` en cada fila.

    Returns:
        Cantidad de ops efectivamente aplicadas (NOOP y skips no cuentan).
    """
    applied = 0
    op_kwargs: dict[str, Any] = {
        "semantic_store": semantic_store,
        "procedural_store": procedural_store,
        "source_session_id": source_session_id,
        "audit_store": audit_store,
        "origin_model": origin_model,
        "origin_mode": origin_mode,
    }
    for op in ops:
        if op.op == "NOOP":
            continue
        try:
            if session is not None:
                # SAVEPOINT por-op: aisla la op + su audit (atomico-o-nada) y evita
                # envenenar la transaccion de las ops siguientes ante un fallo.
                async with session.begin_nested():
                    did_apply = await _apply_single_op(op, **op_kwargs)
            else:
                did_apply = await _apply_single_op(op, **op_kwargs)
            if did_apply:
                applied += 1
        except Exception:
            # La op (o su audit) fallo: el savepoint ya revirtio ESTA op. Se loguea
            # SIN contenido (regla #4) a WARNING para que un fallo de auditoria NO
            # quede invisible, y se sigue con la proxima op.
            logger.warning("memory_engine: op %s/%s revertida (savepoint), skip", op.op, op.layer)
            continue

    return applied


async def _apply_single_op(
    op: MemoryOp,
    *,
    semantic_store: Any,
    procedural_store: Any,
    source_session_id: UUID | None,
    audit_store: AuditStore | None,
    origin_model: LlmModel | None,
    origin_mode: Mode | None,
) -> bool:
    """Aplica UNA op (memoria + su fila de audit) y devuelve ``True`` si cambio el estado.

    Corre DENTRO del savepoint del caller (ver ``apply_ops``): si la op o su audit
    fallan, el ``begin_nested`` revierte AMBAS y el caller NO la cuenta. NOOP/skip
    devuelven ``False`` sin escribir nada. El ``record_hash`` es siempre sha256 hex
    (regla #4: digest, no contenido); ``sensitive=False`` (apply_ops no toca
    episodica, donde vive lo sensible).
    """

    async def _audit(
        *,
        operation: AuditOperation,
        target_layer: MemoryLayer,
        target_id: UUID | None,
        record_hash: str,
    ) -> None:
        if audit_store is not None:
            await audit_store.record(
                operation=operation,
                target_layer=target_layer,
                target_id=target_id,
                record_hash=record_hash,
                origin_model=origin_model,
                origin_mode=origin_mode,
                sensitive=False,
            )

    if op.layer == "semantic":
        if op.op == "ADD":
            if not op.content:
                return False
            # source_session_id SOLO aca (provenance del hecho nuevo). NO en
            # UPDATE/DELETE: un update refina el texto pero no cambia de que sesion
            # vino el hecho original (M10 Ola 1).
            out = await semantic_store.add(
                SemanticMemoryCreate(content=op.content, source_session_id=source_session_id)
            )
            await _audit(
                operation=AuditOperation.WRITE,
                target_layer=MemoryLayer.SEMANTIC,
                target_id=out.id,
                record_hash=compute_record_hash(op.content),
            )
            return True
        if op.op == "UPDATE":
            if not op.target_id or not op.content:
                return False
            result = await semantic_store.update(UUID(op.target_id), op.content)
            if result is None:
                return False
            await _audit(
                operation=AuditOperation.UPDATE,
                target_layer=MemoryLayer.SEMANTIC,
                target_id=result.id,
                record_hash=compute_record_hash(op.content),
            )
            return True
        if op.op == "DELETE":
            if not op.target_id:
                return False
            deleted = await semantic_store.delete(UUID(op.target_id))
            if not deleted:
                return False
            await _audit(
                operation=AuditOperation.DELETE,
                target_layer=MemoryLayer.SEMANTIC,
                target_id=UUID(op.target_id),
                record_hash=compute_record_hash(op.target_id),
            )
            return True
        return False

    if op.layer == "procedural":
        if op.op in ("ADD", "UPDATE"):
            if not op.key or op.value is None:
                return False
            out = await procedural_store.upsert(ProceduralMemoryUpsert(key=op.key, value=op.value))
            # ADD -> WRITE, UPDATE -> UPDATE (ambos van al mismo upsert; la semantica
            # de la op distingue la operacion auditada).
            operation = AuditOperation.WRITE if op.op == "ADD" else AuditOperation.UPDATE
            await _audit(
                operation=operation,
                target_layer=MemoryLayer.PROCEDURAL,
                target_id=out.id,
                record_hash=compute_record_hash(procedural_hash_payload(op.key, op.value)),
            )
            return True
        if op.op == "DELETE":
            if not op.key:
                return False
            deleted = await procedural_store.delete(op.key)
            if not deleted:
                return False
            # target_id=None: la procedural se identifica por key; el delete-by-key no
            # retorna id, y record_hash=sha256(key) ya ata la fila a la entrada borrada.
            await _audit(
                operation=AuditOperation.DELETE,
                target_layer=MemoryLayer.PROCEDURAL,
                target_id=None,
                record_hash=compute_record_hash(op.key),
            )
            return True
        return False

    return False
