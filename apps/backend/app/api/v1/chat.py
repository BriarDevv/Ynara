"""Endpoint HTTP del chat: ``POST /v1/chat``.

Ensambla el ciclo de vida de la ``ChatSession`` (``resolve_chat_session``) con
el router LLM (``app.llm.router.route``) y devuelve un ``ChatHttpResponse``.

Decisiones de diseno M9 (criticadas adversarialmente, NO re-litigar):

(1) Orden transaccional (fix del bug de commit-temprano). El cuerpo hace, en
    orden EXACTO: ``resolve_chat_session`` (flush, obtiene el id sin commit) ->
    ``route()`` -> ``session.commit()`` AL FINAL, DESPUES de ``route()``.
    ``route()`` NUNCA propaga errores del LLM (captura overflow / errores
    permanentes y devuelve un fallback), asi que commitear despues es seguro y
    evita ``ChatSession`` huerfanas si el modelo fallara. Si saltara una
    excepcion inesperada (bug real, no del LLM), ``get_db()`` hace rollback y la
    sesion no se persiste. NO se commitea antes de ``route()``.

(2) Sin historial multi-turno. ``route()`` arma ``messages`` desde cero (system
    + user actual) en cada request: "sin historial multi-turno" significa que
    ``route()`` NO usa turnos previos como contexto, NO que no se persistan. Los
    turnos SI se persisten (USER + MODEL via ``ConversationTurnStore`` en el step
    3.5 de ``_run_chat_turn``, issue #209), como fuente que el worker episodico
    (``consolidate_session``) lee al cerrar la sesion. El ``sessions.id`` es el
    ancla (FK de los turnos y de la episodica / ``source_session_id``). M10 Ola 0:
    el enqueue de consolidacion ocurre DESPUES del ``commit`` (ver
    ``_run_chat_turn``), asi que la fila ya esta persistida cuando el worker
    procesa el turno (sin race con el commit ni ``ForeignKeyViolation`` bajo carga).

(3) Aislamiento por usuario. El ``user_id`` sale del JWT (``CurrentUser``); una
    ``ChatSession`` de otro usuario o inexistente da 404 (sin oraculo de
    existencia ajena) y un ``mode`` distinto al de la sesion abierta da 409.
    Esa logica vive en ``resolve_chat_session``.

(4) ``actions`` defensivas. ``route()`` devuelve ``list[dict]`` crudo del tool
    loop; ``_to_http_actions`` valida cada item contra ``Action`` y descarta los
    malformados (no filtra basura al cliente, pero tampoco rompe la respuesta).

Mapeo de errores (decision #7): 422 validacion (Pydantic, automatico), 401 sin
token / token invalido (``get_current_user``), 404 sesion ajena/inexistente, 409
mode mismatch, 200 + fallback ante overflow/error del LLM (``route()`` ya lo
captura), 500 solo ante un bug no anticipado (Sentry ``before_send`` scrubea).

Streaming (M9 Ola 3): ``POST /v1/chat/stream`` re-emite la MISMA respuesta del
turno como un stream SSE con eventos con nombre (``token`` / ``done`` /
``error``) que el parser de ``packages/shared-schemas/src/sse.ts`` consume. El
trabajo transaccional (DB + commit) es identico a ``/chat`` y ocurre ENTERO
antes de construir el ``StreamingResponse``; el generator solo serializa
primitivos ya snapshoteados. Ver el docstring de ``chat_stream`` para el porque
de retornar un ``StreamingResponse`` explicito y del snapshot de primitivos.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._http import too_many_requests
from app.api.v1._sessions import resolve_chat_session
from app.core.config import get_settings
from app.core.deps import (
    CurrentUser,
    DbSession,
    TokenStoreDep,
    get_embedder,
    get_llm_client,
    get_reranker,
)
from app.core.ratelimit import check_chat_rate_limit
from app.enums import TurnRole
from app.llm.clients.base import LLMClient
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.llm.config import load_llm_config
from app.llm.router import route
from app.llm.schemas import ChatRequest, ChatResponse
from app.memory.conversation_turns import ConversationTurnStore
from app.models.session import ChatSession
from app.schemas.chat import Action, ChatHttpRequest, ChatHttpResponse
from app.schemas.conversation_turn import ConversationTurnCreate
from app.workflows.consolidation import consolidate_turn

logger = logging.getLogger(__name__)

router = APIRouter()

# Tamano de ventana (en code-points) de cada chunk ``token`` del stream SSE. El
# texto se trocea en ventanas de N code-points; ``''.join(deltas)`` reconstruye
# ``resp.text`` byte-a-byte (invariante dura del wire).
_TOKEN_CHUNK_SIZE = 6

# Codigo + mensaje del evento ``error`` (red de seguridad del generator). Neutro,
# sin PII ni detalle tecnico (regla #4): el message viaja al cliente.
_STREAM_ERROR_CODE = "stream_error"
_STREAM_ERROR_MESSAGE = "No se pudo completar la respuesta"


def _to_http_actions(raw: list[dict]) -> list[Action]:
    """Convierte las actions crudas de ``route()`` en ``Action`` del wire.

    El tool loop produce dicts ``{'id', 'name', 'arguments', 'result'}``;
    validamos cada item contra ``Action`` y descartamos los malformados (no se
    filtra basura al cliente). Conversion DEFENSIVA: un dict que no valide no
    debe tumbar toda la respuesta.
    """
    actions: list[Action] = []
    for item in raw:
        try:
            actions.append(Action.model_validate(item))
        except ValidationError:
            # Action malformada: se descarta silenciosamente (no se expone basura).
            continue
    return actions


async def _run_chat_turn(
    *,
    session: AsyncSession,
    user_id: UUID,
    body: ChatHttpRequest,
    llm_client: LLMClient,
    embedder: EmbeddingClient,
    reranker: Reranker,
) -> tuple[ChatSession, ChatResponse]:
    """Ejecuta el trabajo transaccional de un turno de chat y devuelve crudos.

    Helper compartido por ``/chat`` y ``/chat/stream``: ambos hacen EXACTAMENTE
    el mismo trabajo de DB + router + commit; la unica diferencia es como
    serializan el resultado (``ChatHttpResponse`` vs eventos SSE). Devolver la
    ``ChatSession`` y el ``ChatResponse`` crudos (sin armar el wire) mantiene
    ese ensamblado en los endpoints.

    Orden transaccional (decision #2 M9 + M10 Ola 0):
    ``resolve_chat_session`` (flush, sin commit) -> ``route()`` ->
    ``session.commit()`` DESPUES de ``route()`` -> ``consolidate_turn.delay()``
    DESPUES del commit. Es seguro commitear al final porque ``route()`` nunca
    propaga errores del LLM (overflow / error permanente devuelven fallback); asi
    se evita persistir una ``ChatSession`` huerfana y se mantiene el commit unico
    por request. Si saltara un bug inesperado antes del commit, ``get_db()`` hace
    rollback y nada se persiste (ni se encola: el enqueue es lo ultimo).

    Enqueue post-commit (M10 Ola 0): el ``consolidate_turn.delay()`` se movio de
    ``route()`` a aca, DESPUES del commit, para que la ``ChatSession`` ya este
    persistida antes de que el worker Celery (otro proceso) procese el turno.
    Hoy es inocuo (la task no toca FKs a ``sessions``), pero blinda a M10 cuando
    escriba ``source_session_id`` / ``episodic.session_id`` (FK a ``sessions.id``)
    contra un race enqueue-vs-commit. Sede UNICA: ``/chat`` y ``/chat/stream``
    heredan el enqueue. Misma condicion que tenia ``route()`` (``writes_memory``
    + turno no-degradado); mismos kwargs.

    Sin historial multi-turno: ``route()`` arma ``messages`` desde cero (system
    + user actual) en cada llamada y NO usa turnos previos como contexto. Eso NO
    significa que no se persistan: los 2 turnos (USER + MODEL) SI se guardan en el
    step 3.5 via ``ConversationTurnStore`` (issue #209), en la misma transaccion
    que la ``ChatSession``. El ``session_id`` es el ancla (FK de los turnos), no
    historial vivo que el router reinyecte.

    Returns:
        Tupla ``(chat_session, resp)``: la ``ChatSession`` persistida (su
        ``id`` ya esta asignado) y el ``ChatResponse`` crudo del router. NO se
        arma ``ChatHttpResponse`` ni SSE aca.
    """
    # (1) Resolver (crear o validar) la sesion. flush, NO commit: el id queda
    #     asignado por el ORM; el commit es al final del turno.
    chat_session = await resolve_chat_session(
        session,
        user_id=user_id,
        session_id=body.session_id,
        mode=body.mode,
    )

    # (2) Traducir al contrato de dominio del router. session_id va como str del
    #     UUID real de la ChatSession (el router lo trata opaco).
    domain_req = ChatRequest(
        text=body.text,
        mode=body.mode,
        session_id=str(chat_session.id),
    )

    # (3) Router LLM. NUNCA propaga errores del LLM (captura overflow / error
    #     permanente y devuelve fallback), por eso es seguro commitear despues.
    resp = await route(
        domain_req,
        session=session,
        user_id=user_id,
        llm_client=llm_client,
        embedder=embedder,
        reranker=reranker,
    )

    # (3.5) Persistir los 2 turnos (user + modelo) ANTES del commit, en la MISMA
    #       transaccion que la ChatSession (commit unico del paso 4): turnos +
    #       sesion son atomicos. El content viaja cifrado per-user (regla #4) via
    #       ConversationTurnStore. Es la FUENTE que el worker episodico
    #       (consolidate_session) lee al cerrar la sesion para resumir (issue #209).
    #
    #       Sede UNICA: /chat y /chat/stream pasan por aca, asi que ambos persisten
    #       los turnos. NO se persiste si el turno DEGRADO (resp.finish_reason ==
    #       'degraded': fallback de route() por error LLM o cadena on-prem agotada):
    #       un turno degradado no tiene una respuesta util que valga la pena
    #       resumir, igual que no se encola consolidate_turn (paso 5). Tampoco si la
    #       respuesta del modelo quedo vacia (turno sin contenido util): el schema
    #       ConversationTurnCreate exige content no-vacio, y un turno vacio no aporta
    #       al resumen episodico.
    if resp.finish_reason != "degraded" and resp.text:
        turns_store = ConversationTurnStore(session, user_id)
        # seq POR SESION (no hardcodeado): el proximo libre es MAX(seq)+1 de la
        # sesion (0 si esta vacia). Hardcodear 0/1 rompia el SEGUNDO turno de una
        # sesion reusada (session_id en el body -> resolve_chat_session REUSA la
        # ChatSession) con IntegrityError sobre UniqueConstraint(session_id, seq)
        # en el flush -> rollback -> 500 y turno perdido (issue #209). El turno user
        # va en ``base`` y el del modelo en ``base+1``: secuencia monotonica
        # alternada user/model a lo largo de la sesion.
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

    # (4) Commit AL FINAL, despues de route(): persiste la ChatSession + los turnos
    #     (y lo que hayan escrito los stores en esta sesion). Si saltara un bug
    #     inesperado antes de aca, get_db() hace rollback y nada se persiste.
    await session.commit()

    # (5) Enqueue de consolidacion DESPUES del commit (M10 Ola 0). Se movio aca
    #     desde route() para garantizar que la ChatSession ya este persistida
    #     antes de que el worker Celery (otro proceso) lea el turno: un enqueue
    #     pre-commit puede ganarle al commit y, el dia que M10 escriba una FK a
    #     sessions.id (source_session_id / episodic.session_id), seria un
    #     ForeignKeyViolation reproducible bajo carga. .delay() es no-bloqueante.
    #
    #     MISMA condicion que tenia route() (no se re-litiga): encolar SOLO si el
    #     modelo del modo escribe memoria (writes_memory: Qwen=True, Gemma=False)
    #     y el turno NO degrado. finish_reason 'degraded' lo produce el fallback de
    #     route() (error LLM) O un CompletionResult degradado del cliente (cadena de
    #     fallback on-prem agotada); en ambos casos NO consolidamos. Un turno con
    #     'max_iterations' NO es degradado y SI consolida.
    #
    #     Esta es la UNICA sede de enqueue: ambos endpoints (/chat y /chat/stream)
    #     pasan por _run_chat_turn, asi que los dos heredan el enqueue post-commit.
    #     NUNCA meter el .delay() en el generator SSE del endpoint: el commit ya
    #     ocurrio aca y el closure del stream solo cierra sobre primitivos.
    #
    #     Fail-open (doctrina del stack, igual que el TokenStore que degrada en vez
    #     de romper): .delay() publica al broker Redis de forma SINCRONA; si Redis
    #     esta caido tira OperationalError / ConnectionError / errores de kombu. El
    #     turno YA esta commiteado (paso 4): un fallo del enqueue NO debe devolver
    #     500 con el turno persistido. La consolidacion es eventual, asi que perder
    #     un enqueue es degradacion aceptable. Capturamos AMPLIO (Exception) porque
    #     .delay() puede tirar varios tipos, y logueamos SOLO type(exc).__name__
    #     (regla #4: jamas payload / args / str(exc)). Solo el enqueue va en el
    #     try: nada anterior al commit se captura aca.
    writes_memory = load_llm_config().model_for_mode(body.mode.value).writes_memory
    if writes_memory and resp.finish_reason != "degraded":
        try:
            consolidate_turn.delay(
                user_id=str(user_id),
                session_id=str(chat_session.id),
                user_msg=body.text,
                model_response=resp.text,
                mode=body.mode.value,
            )
        except Exception as exc:  # best-effort: el broker caido NO rompe el turno.
            logger.warning("consolidate_turn enqueue failed: %s", type(exc).__name__)

    return chat_session, resp


@router.post("/chat", response_model=ChatHttpResponse, status_code=200)
async def chat(
    body: ChatHttpRequest,
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
    llm_client: Annotated[LLMClient, Depends(get_llm_client)],
    embedder: Annotated[EmbeddingClient, Depends(get_embedder)],
    reranker: Annotated[Reranker, Depends(get_reranker)],
) -> ChatHttpResponse:
    """Procesa un turno de chat: resuelve la sesion, invoca el router y responde.

    Delega el trabajo transaccional (DB + router + commit) en ``_run_chat_turn``
    y arma la respuesta wire ``ChatHttpResponse``. actions defensivas
    (decision #4): se descartan las malformadas, no se filtra basura al cliente.

    Rate-limit (S4, P1 seguridad): bucket por ``user_id`` (del JWT ya autenticado),
    ANTES de tocar la DB. fail-open si Redis cae (sin freno, baseline). 429 con
    ``Retry-After`` (mismo shape que ``auth.py``) si se cruza el techo de la ventana.

    Returns:
        ``ChatHttpResponse`` con el texto final, las ``actions`` ejecutadas
        (validadas), el ``session_id`` (UUID de la ``ChatSession``) y el
        ``finish_reason`` del router.
    """
    if not await check_chat_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().chat_window_seconds)
    chat_session, resp = await _run_chat_turn(
        session=session,
        user_id=user_id,
        body=body,
        llm_client=llm_client,
        embedder=embedder,
        reranker=reranker,
    )
    return ChatHttpResponse(
        text=resp.text,
        actions=_to_http_actions(resp.actions),
        session_id=chat_session.id,
        finish_reason=resp.finish_reason,
    )


def _sse_event(name: str, payload: dict[str, Any]) -> str:
    """Serializa un evento SSE con nombre al wire que consume ``sse.ts``.

    Formato: ``event: <name>\\ndata: <json>\\n\\n``. El ``data`` SIEMPRE pasa por
    ``json.dumps(ensure_ascii=False)``: un ``'\\n'`` crudo dentro del payload
    partiria el bloque SSE (el separador de bloques es ``'\\n\\n'``), asi que
    nunca se interpola texto crudo. El doble ``'\\n\\n'`` final cierra el bloque.
    """
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def chat_stream(
    body: ChatHttpRequest,
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
    llm_client: Annotated[LLMClient, Depends(get_llm_client)],
    embedder: Annotated[EmbeddingClient, Depends(get_embedder)],
    reranker: Annotated[Reranker, Depends(get_reranker)],
) -> StreamingResponse:
    """Re-emite el turno de chat como stream SSE con eventos con nombre.

    Mismo contrato de turno que ``/chat`` (mismo ``_run_chat_turn``); la
    diferencia es el wire: en vez de un JSON ``ChatHttpResponse``, emite el
    stream SSE que consume ``packages/shared-schemas/src/sse.ts``::

        event: token
        data: {"delta": "Hola"}

        event: done
        data: {"session_id": "...", "actions": [...], "finish_reason": "stop"}

    Diseno (NO re-litigar):

    (1) Orden: TODO el trabajo transaccional (DB + commit) ocurre ANTES de
        construir el ``StreamingResponse``. Si algo falla aca (incluido el
        ``commit``), la excepcion propaga ANTES de devolver la response ->
        ``get_db()`` hace rollback -> 500 limpio con 0 bytes SSE (el stream
        nunca arranco). Los errores de validacion / auth / sesion
        (422 / 401 / 404 / 409) saltan aca como HTTP normales, NO como eventos
        SSE: el cliente los ve como status codes, no como ``event: error``.

    (2) Snapshot de primitivos ANTES del generator. El closure del generator
        cierra SOLO sobre ``str`` / ``list[dict]`` ya serializados; NUNCA sobre
        ``chat_session`` ni atributos ORM. Despues del ``commit`` un acceso
        lazy a un atributo ORM podria disparar I/O sobre una sesion ya cerrada
        (lazy-load post-commit). Snapshotear los primitivos lo evita de raiz.

    (3) ``StreamingResponse`` EXPLICITO, no un endpoint async-gen ni
        ``EventSourceResponse``. NO convertir esto a SSE nativo de FastAPI: a
        partir de 0.136 FastAPI tiene su propio soporte SSE que cambiaria tanto
        el wire (formato de los eventos) como el lifecycle (cuando corre el
        generator vs cuando se cierra la sesion DB). Devolver el
        ``StreamingResponse`` a mano fija el contrato exacto que ``sse.ts``
        espera; un refactor futuro NO debe 'modernizarlo'.

    Returns:
        ``StreamingResponse`` ``text/event-stream`` que emite N eventos
        ``token`` (ventanas de ``_TOKEN_CHUNK_SIZE`` code-points del texto)
        seguidos de un evento ``done``. Si el texto es vacio: 0 tokens + 1 done.
    """
    # (0) Rate-limit por user_id (S4, P1 seguridad), ANTES de tocar la DB: el 429
    #     salta como HTTP normal (no como event: error SSE), igual que 401/404/409.
    #     fail-open si Redis cae (sin freno, baseline). Mismo bucket que /chat.
    if not await check_chat_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().chat_window_seconds)

    # (1) Mismo trabajo transaccional que /chat. Si algo falla aca (incl. commit)
    #     propaga ANTES del StreamingResponse -> get_db rollback -> 500 limpio,
    #     0 bytes SSE. 422/401/404/409 saltan aca como HTTP normales.
    chat_session, resp = await _run_chat_turn(
        session=session,
        user_id=user_id,
        body=body,
        llm_client=llm_client,
        embedder=embedder,
        reranker=reranker,
    )

    # (2) SNAPSHOT de primitivos puros ANTES del generator. NUNCA se pasa
    #     chat_session ni atributos ORM al closure (evita lazy-load post-commit).
    text: str = resp.text
    session_id_str: str = str(chat_session.id)
    actions_payload: list[dict[str, Any]] = [
        a.model_dump(mode="json") for a in _to_http_actions(resp.actions)
    ]
    # Coercion D4: finish_reason None -> 'stop'; 'degraded' se preserva tal cual.
    finish_reason: str = resp.finish_reason or "stop"
    done_payload: dict[str, Any] = {
        "session_id": session_id_str,
        "actions": actions_payload,
        "finish_reason": finish_reason,
    }

    # (3) Generator: cierra SOLO sobre str / list[dict] ya serializados. El
    #     try/except es una red de seguridad (regla #4, sin PII); en la practica
    #     improbable porque todo el payload esta pre-serializado.
    async def _gen() -> AsyncIterator[str]:
        try:
            for i in range(0, len(text), _TOKEN_CHUNK_SIZE):
                yield _sse_event("token", {"delta": text[i : i + _TOKEN_CHUNK_SIZE]})
            # text vacio -> el for no itera -> 0 tokens (D7). Igual se emite done.
            yield _sse_event("done", done_payload)
        except Exception:  # red de seguridad; todo esta pre-serializado.
            yield _sse_event(
                "error",
                {"code": _STREAM_ERROR_CODE, "message": _STREAM_ERROR_MESSAGE},
            )

    # (4) RETORNAR StreamingResponse explicito (NO async-gen endpoint, NO
    #     EventSourceResponse): fija el wire + lifecycle que espera sse.ts.
    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
