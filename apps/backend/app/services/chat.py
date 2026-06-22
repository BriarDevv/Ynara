"""Service del turno de chat: orquestación transaccional de ``POST /v1/chat[/stream]``.

Capa de dominio entre los endpoints (``app/api/v1/chat.py``) y el router LLM +
los stores. Ejecuta el trabajo transaccional de UN turno sobre una ``ChatSession``
**ya resuelta**: invoca el router LLM, persiste los 2 turnos (user + modelo),
commitea y encola la consolidación DESPUÉS del commit. NO importa FastAPI (como
``services/auth.py``).

Reparto router ↔ service:

- **Router (HTTP):** inyección de deps, rate-limit (Redis), resolución del ciclo de
  vida de la ``ChatSession`` (``resolve_chat_session``: crea/valida + 404/409 — vive
  en el borde HTTP porque levanta ``HTTPException``), y el wire (``ChatHttpResponse``
  o el stream SSE). El ``commit`` ocurre dentro de ``run_turn`` (ver más abajo).
- **Service (dominio):** ``run_turn`` = router LLM → persistir turnos → commit →
  enqueue post-commit.

Orden transaccional (decisión #2 M9 + M10 Ola 0):
``resolve_chat_session`` (flush en el router, asigna el id sin commit) → ``route()``
→ ``session.commit()`` DESPUÉS de ``route()`` → ``consolidate_turn.delay()`` DESPUÉS
del commit. Es seguro commitear al final porque ``route()`` NUNCA propaga errores del
LLM (overflow / error permanente devuelven fallback): así se evita persistir una
``ChatSession`` huérfana y se mantiene el commit único por request. Si saltara un bug
inesperado antes del commit, ``get_db()`` hace rollback y nada se persiste (ni se
encola: el enqueue es lo último). El ``commit`` queda JUNTO al enqueue (no en el
endpoint) porque el enqueue-post-commit es un invariante de dominio: separarlos
rompería la garantía de "encolar solo después de persistir".

Tools SÍNCRONAS en el turno (ADR-022): las tools de agente (``calendar``/``task``) ya
NO se accionan async por detrás. ``route()`` corre el tool-loop de producción con el
registry REAL (``build_chat_tool_registry`` vía ``build_memory_context``): las tool
calls que el modelo emita ESCRIBEN dentro de ``route()`` sobre ESTA misma sesión, y el
``session.commit()`` de abajo las persiste atómicas con el turno (un solo commit). Por
eso ``run_turn`` ya NO encola ``agent_turn_pass`` (seguir haciéndolo dispararía qwen
DOS veces por turno; ver ADR-022). La consolidación de MEMORIA sí sigue async
(``_enqueue_consolidation``, gateada por ``writes_memory``): no cambia.

SAVEPOINT en turnos degradados (fix de la consecuencia negativa de ADR-022): ``route()``
nunca propaga el ``LlmError`` (devuelve ``finish_reason='degraded'``), pero una tool pudo
haber flusheado un ``calendar_event`` / ``task`` ANTES de que el LLM degradara (en esa o
en una iteración posterior del tool-loop). Para no commitear un evento/tarea fantasma sin
un turno de conversación que lo confirme, ``run_turn`` envuelve ``route()`` en un
``begin_nested()`` (SAVEPOINT): en un turno degradado se hace ``rollback()`` del nested
(descarta SOLO las escrituras de tools; la ``ChatSession`` queda afuera y sobrevive como
ancla), y en el camino feliz se libera el SAVEPOINT y el commit único persiste todo
atómico. Cubre TODOS los puntos donde ``route()`` captura un ``LlmError`` (no solo "una
iteración posterior"), eliminando el desajuste DB-tiene-evento / turnos-vacíos.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import TurnRole
from app.llm.clients.base import LLMClient
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.llm.config import load_llm_config
from app.llm.router import route
from app.llm.schemas import ChatRequest, ChatResponse
from app.memory.conversation_turns import ConversationTurnStore
from app.models.session import ChatSession
from app.schemas.chat import ChatHttpRequest
from app.schemas.conversation_turn import ConversationTurnCreate
from app.workflows.consolidation import consolidate_turn

logger = logging.getLogger(__name__)


class ChatService:
    """Ejecuta el turno de chat de UN usuario sobre una ``ChatSession`` resuelta.

    Recibe las deps por argumento (sesión async + ``user_id`` del JWT + los clientes
    LLM/embedder/reranker), igual que el router pasaba a ``route()``. Sin estado entre
    turnos: una instancia por request.
    """

    def __init__(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        llm_client: LLMClient,
        embedder: EmbeddingClient,
        reranker: Reranker,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._llm_client = llm_client
        self._embedder = embedder
        self._reranker = reranker

    async def run_turn(self, chat_session: ChatSession, body: ChatHttpRequest) -> ChatResponse:
        """Ejecuta el trabajo transaccional de un turno y devuelve el ``ChatResponse`` crudo.

        Helper compartido por ``/chat`` y ``/chat/stream``: ambos hacen EXACTAMENTE el
        mismo trabajo de router + commit; la única diferencia es cómo serializan el
        resultado (``ChatHttpResponse`` vs eventos SSE). Devolver el ``ChatResponse``
        crudo (sin armar el wire) mantiene ese ensamblado en los endpoints; el
        ``chat_session`` ya lo tiene el endpoint (lo resolvió antes de llamar acá).

        Orden: ``route()`` → persistir turnos → ``commit`` → enqueue de consolidación
        post-commit (ver el docstring del módulo). El ``chat_session`` llega YA resuelto
        y flusheado por el router (su ``id`` está asignado).

        Tools SÍNCRONAS (ADR-022): las tool calls de agente (``calendar``/``task``) que
        el modelo emita se EJECUTAN dentro de ``route()`` (tool-loop de producción con el
        registry real) sobre esta misma sesión, y el ``commit`` de abajo las persiste
        atómicas con el turno. Por eso NO se encola ``agent_turn_pass``: el efecto ya
        ocurrió y el modelo pudo confirmarlo en su respuesta ("listo, te agendé...").

        Returns:
            El ``ChatResponse`` crudo del router. NO arma ``ChatHttpResponse`` ni SSE.
        """
        # Traducir al contrato de dominio del router. session_id va como str del UUID
        # real de la ChatSession (el router lo trata opaco).
        domain_req = ChatRequest(
            text=body.text,
            mode=body.mode,
            session_id=str(chat_session.id),
        )

        # Router LLM. NUNCA propaga errores del LLM (captura overflow / error permanente
        # y devuelve fallback), por eso es seguro commitear después.
        #
        # SAVEPOINT alrededor de route() (ADR-022, fix del commit de tool degradado): las
        # tools de agente (``calendar``/``task``) hacen ``flush`` dentro de ``route()`` sobre
        # ESTA sesión. Si el turno DEGRADA (``route()`` capturó un ``LlmError`` en CUALQUIER
        # punto, incluida una iteración posterior del tool-loop después de que una tool ya
        # flusheó), no queremos commitear un evento/tarea fantasma sin un turno de
        # conversación que lo confirme. El savepoint acota las escrituras de las tools: en un
        # turno degradado se hace ``rollback()`` del nested para descartar SOLO esas
        # escrituras (la ``ChatSession`` flusheada por el router queda fuera del savepoint y
        # sobrevive como ancla de la sesión). En el camino feliz el savepoint se libera con
        # ``commit()`` del nested (no commitea a disco; solo libera el SAVEPOINT) y el commit
        # único de abajo persiste todo atómico.
        savepoint = await self._session.begin_nested()
        resp = await route(
            domain_req,
            session=self._session,
            user_id=self._user_id,
            llm_client=self._llm_client,
            embedder=self._embedder,
            reranker=self._reranker,
        )
        if resp.finish_reason == "degraded":
            # Turno degradado: descartar las escrituras de tools flusheadas dentro del
            # savepoint (evita el evento/tarea fantasma sin turno que lo confirme).
            await savepoint.rollback()
        else:
            # Camino feliz: liberar el SAVEPOINT (no es un commit a disco). El commit único
            # de abajo persiste las escrituras de tools + el turno atómicos.
            await savepoint.commit()

        # Persistir los 2 turnos (user + modelo) ANTES del commit, en la MISMA
        # transacción que la ChatSession: turnos + sesión son atómicos por el commit único.
        if resp.finish_reason != "degraded" and resp.text:
            await self._persist_turns(chat_session, body=body, resp=resp)

        # Commit AL FINAL, después de route(): persiste la ChatSession + los turnos (y lo
        # que hayan escrito los stores en esta sesión). Si saltara un bug inesperado antes
        # de acá, get_db() hace rollback y nada se persiste.
        await self._session.commit()

        # Enqueue de consolidación DESPUÉS del commit (M10 Ola 0): garantiza que la
        # ChatSession ya esté persistida antes de que el worker Celery (otro proceso) lea
        # el turno. .delay() es no-bloqueante y fail-open (ver _enqueue_consolidation).
        #
        # NO se encola ``agent_turn_pass`` (ADR-022): las tools de agente
        # (``calendar``/``task``) ya se ejecutaron SÍNCRONAS dentro de ``route()`` (el
        # tool-loop de producción usa el registry real vía ``build_chat_tool_registry``)
        # y se commitearon atómicas con el turno arriba. Seguir encolando la pasada async
        # dispararía qwen DOS veces por turno. La consolidación de memoria SÍ sigue async.
        await self._enqueue_consolidation(chat_session, body=body, resp=resp)

        return resp

    async def _persist_turns(
        self, chat_session: ChatSession, *, body: ChatHttpRequest, resp: ChatResponse
    ) -> None:
        """Persiste el turno USER + el del MODELO (cifrados per-user) en la sesión actual.

        Es la FUENTE que el worker episódico (``consolidate_session``) lee al cerrar la
        sesión para resumir (issue #209). El content viaja cifrado per-user (regla #4) vía
        ``ConversationTurnStore``. NO se llama si el turno DEGRADÓ o si la respuesta del
        modelo quedó vacía (el caller ya chequea ``finish_reason != 'degraded' and resp.text``):
        un turno degradado/vacío no tiene una respuesta útil que valga la pena resumir.

        ``seq`` POR SESIÓN (no hardcodeado): el próximo libre es ``MAX(seq)+1`` de la
        sesión (0 si está vacía). Hardcodear 0/1 rompía el SEGUNDO turno de una sesión
        reusada con IntegrityError sobre ``UniqueConstraint(session_id, seq)`` en el flush
        → rollback → 500 y turno perdido (issue #209). El turno user va en ``base`` y el del
        modelo en ``base+1``: secuencia monotónica alternada user/model a lo largo de la sesión.
        """
        turns_store = ConversationTurnStore(self._session, self._user_id)
        base = await turns_store.next_seq(chat_session.id)
        await turns_store.add(
            ConversationTurnCreate(
                session_id=chat_session.id,
                role=TurnRole.USER,
                content=body.text,
                seq=base,
            )
        )
        await turns_store.add(
            ConversationTurnCreate(
                session_id=chat_session.id,
                role=TurnRole.MODEL,
                content=resp.text,
                seq=base + 1,
            )
        )

    async def _enqueue_consolidation(
        self, chat_session: ChatSession, *, body: ChatHttpRequest, resp: ChatResponse
    ) -> None:
        """Encola ``consolidate_turn`` DESPUÉS del commit (M10 Ola 0), best-effort.

        MISMA condición que tenía ``route()`` (no se re-litiga): encolar SOLO si el modelo
        del modo escribe memoria (``writes_memory``: Qwen=True, Gemma=False) y el turno NO
        degradó. ``finish_reason 'degraded'`` lo produce el fallback de ``route()`` (error
        LLM) o un ``CompletionResult`` degradado (cadena de fallback on-prem agotada); en
        ambos casos NO consolidamos. Un turno con ``'max_iterations'`` NO es degradado y SÍ
        consolida.

        Fail-open (doctrina del stack): ``.delay()`` publica al broker Redis de forma
        SÍNCRONA; si Redis está caído tira ``OperationalError`` / ``ConnectionError`` /
        errores de kombu. El turno YA está commiteado: un fallo del enqueue NO debe devolver
        500 con el turno persistido. La consolidación es eventual, así que perder un enqueue
        es degradación aceptable. Capturamos AMPLIO (``Exception``) porque ``.delay()`` puede
        tirar varios tipos, y logueamos SOLO ``type(exc).__name__`` (regla #4: jamás payload /
        args / str(exc)).
        """
        writes_memory = load_llm_config().model_for_mode(body.mode.value).writes_memory
        if not (writes_memory and resp.finish_reason != "degraded"):
            return
        try:
            consolidate_turn.delay(
                user_id=str(self._user_id),
                session_id=str(chat_session.id),
                user_msg=body.text,
                model_response=resp.text,
                mode=body.mode.value,
            )
        except Exception as exc:  # best-effort: el broker caído NO rompe el turno.
            logger.warning("consolidate_turn enqueue failed: %s", type(exc).__name__)
