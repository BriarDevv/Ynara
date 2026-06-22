"""Endpoints HTTP del chat: ``POST /v1/chat`` y ``POST /v1/chat/stream``.

Capa FINA: resuelve el ciclo de vida de la ``ChatSession`` (``resolve_chat_session``),
delega el trabajo transaccional del turno en ``ChatService`` (``app/services/chat.py``)
y serializa el resultado (``ChatHttpResponse`` o el stream SSE). El router se queda con
lo que es HTTP puro; el dominio (router LLM + persistencia de turnos + commit + enqueue
post-commit) vive en el service.

Decisiones de diseno M9 (criticadas adversarialmente, NO re-litigar):

(1) Orden transaccional (fix del bug de commit-temprano). El endpoint hace, en orden
    EXACTO: ``resolve_chat_session`` (flush, obtiene el id sin commit) ->
    ``ChatService.run_turn`` (``route()`` -> persistir turnos -> ``commit`` ->
    enqueue post-commit). ``route()`` NUNCA propaga errores del LLM (captura overflow /
    errores permanentes y devuelve fallback), asi que commitear despues es seguro y
    evita ``ChatSession`` huerfanas. Ver el docstring de ``ChatService`` para el detalle.

(2) Sin historial multi-turno. ``route()`` arma ``messages`` desde cero (system + user
    actual) en cada request: NO usa turnos previos como contexto. Pero los turnos SI se
    persisten (USER + MODEL via ``ConversationTurnStore``, issue #209), como fuente que el
    worker episodico (``consolidate_session``) lee al cerrar la sesion. El ``sessions.id``
    es el ancla (FK de los turnos y de la episodica / ``source_session_id``).

(3) Aislamiento por usuario. El ``user_id`` sale del JWT (``CurrentUser``); una
    ``ChatSession`` de otro usuario o inexistente da 404 (sin oraculo de existencia ajena)
    y un ``mode`` distinto al de la sesion abierta da 409. Esa logica vive en
    ``resolve_chat_session`` (borde HTTP: levanta ``HTTPException``).

(4) ``actions`` defensivas. ``route()`` devuelve ``list[dict]`` crudo del tool loop;
    ``_to_http_actions`` valida cada item contra ``Action`` y descarta los malformados (no
    filtra basura al cliente, pero tampoco rompe la respuesta).

Mapeo de errores (decision #7): 422 validacion (Pydantic, automatico), 401 sin token /
token invalido (``get_current_user``), 404 sesion ajena/inexistente, 409 mode mismatch,
429 rate-limit, 200 + fallback ante overflow/error del LLM (``route()`` ya lo captura),
500 solo ante un bug no anticipado (Sentry ``before_send`` scrubea).

Streaming (M9 Ola 3): ``POST /v1/chat/stream`` re-emite la MISMA respuesta del turno como
un stream SSE con eventos con nombre (``token`` / ``done`` / ``error``) que el parser de
``packages/shared-schemas/src/sse.ts`` consume. El trabajo transaccional (DB + commit, en
``ChatService.run_turn``) es identico a ``/chat`` y ocurre ENTERO antes de construir el
``StreamingResponse``; el generator solo serializa primitivos ya snapshoteados. Ver el
docstring de ``chat_stream`` para el porque de retornar un ``StreamingResponse`` explicito.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

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
from app.core.ratelimit import charge_chat_tool_writes, check_chat_rate_limit
from app.llm.clients.base import LLMClient
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.schemas.chat import Action, ChatHttpRequest, ChatHttpResponse
from app.services.chat import ChatService

router = APIRouter()

# Tamano de ventana (en code-points) de cada chunk ``token`` del stream SSE. El texto se
# trocea en ventanas de N code-points; ``''.join(deltas)`` reconstruye ``resp.text``
# byte-a-byte (invariante dura del wire).
_TOKEN_CHUNK_SIZE = 6

# Codigo + mensaje del evento ``error`` (red de seguridad del generator). Neutro, sin PII
# ni detalle tecnico (regla #4): el message viaja al cliente.
_STREAM_ERROR_CODE = "stream_error"
_STREAM_ERROR_MESSAGE = "No se pudo completar la respuesta"

LlmClientDep = Annotated[LLMClient, Depends(get_llm_client)]
EmbedderDep = Annotated[EmbeddingClient, Depends(get_embedder)]
RerankerDep = Annotated[Reranker, Depends(get_reranker)]


# Tope de ítems de una lista (``events`` / ``tasks``) que viaja en el ``result`` de una
# action hacia el browser. El tool-loop ya acota lo que ve el MODELO (ver
# ``AGENT_LIST_RESULT_LIMIT`` en ``app/llm/tools``), pero el wire del cliente repite el cap
# como defensa en profundidad: ni una respuesta enorme ni un cambio futuro en el límite del
# loop inflan el payload del browser. El front (``MessageActions``) hoy no renderiza el
# contenido de la lista; el cap evita mandar toda la agenda igual.
_CLIENT_RESULT_LIST_LIMIT = 50

# Claves de ``result`` cuyo valor es una lista acotable antes de mandarla al cliente.
_RESULT_LIST_KEYS = ("events", "tasks")


def _sanitize_result(result: object) -> dict[str, Any]:
    """Minimiza el ``result`` crudo de una tool antes de mandarlo al cliente (defensa en prof.).

    Mantiene el CONTRATO del wire (``result`` sigue trayendo el dict del dominio: el front lo
    consumirá a futuro, ver el TODO en ``MessageActions.tsx``) pero recorta las dos fugas
    concretas que la review marcó:

    - ``echo`` de un stub ``not_wired``: es el ``arguments`` del usuario reflejado tal cual
      (``not_wired_result`` lo mete en ``echo``). El front no lo usa; se descarta para no
      reenviar el input derivado del usuario en el payload del stub.
    - listas sin tope (``events`` / ``tasks`` de ``list_*``): se truncan a
      ``_CLIENT_RESULT_LIST_LIMIT`` ítems, así un usuario con miles de filas no infla el
      payload del browser aunque el límite del loop cambie.

    El resto del ``result`` (evento/tarea creados, ``error`` estructurado) pasa sin tocar.
    """
    if not isinstance(result, dict):
        return result if isinstance(result, dict) else {}
    sanitized = dict(result)
    # Stub not_wired: no reenviar el echo de los args del usuario.
    if sanitized.get("status") == "not_wired":
        sanitized.pop("echo", None)
    # Listas acotadas: cap defensivo del payload del cliente.
    for key in _RESULT_LIST_KEYS:
        value = sanitized.get(key)
        if isinstance(value, list) and len(value) > _CLIENT_RESULT_LIST_LIMIT:
            sanitized[key] = value[:_CLIENT_RESULT_LIST_LIMIT]
    return sanitized


def _to_http_actions(raw: list[dict]) -> list[Action]:
    """Convierte las actions crudas de ``route()`` en ``Action`` del wire (sanitizadas).

    El tool loop produce dicts ``{'id', 'name', 'arguments', 'result'}``; validamos cada
    item contra ``Action`` y descartamos los malformados (no se filtra basura al cliente).
    Conversion DEFENSIVA: un dict que no valide no debe tumbar toda la respuesta.

    Minimización del payload del cliente (defensa en profundidad, sin romper el contrato):
    el ``result`` pasa por ``_sanitize_result`` (descarta el ``echo`` del stub + acota listas
    grandes). ``arguments`` se mantiene (el contrato wire documentado lo lleva y el front lo
    consumirá), pero ya no es un vector de fuga ilimitado porque los args de las tools reales
    están acotados en sus schemas (``max_length`` en ``calendar.py`` / ``task.py``).
    """
    actions: list[Action] = []
    for item in raw:
        try:
            validated = Action.model_validate(item)
        except ValidationError:
            # Action malformada: se descarta silenciosamente (no se expone basura).
            continue
        actions.append(validated.model_copy(update={"result": _sanitize_result(validated.result)}))
    return actions


@router.post("/chat", response_model=ChatHttpResponse, status_code=200)
async def chat(
    body: ChatHttpRequest,
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
    llm_client: LlmClientDep,
    embedder: EmbedderDep,
    reranker: RerankerDep,
) -> ChatHttpResponse:
    """Procesa un turno de chat: resuelve la sesion, corre el turno y responde.

    Resuelve la ``ChatSession`` (``resolve_chat_session``), delega el trabajo
    transaccional (router + commit + enqueue) en ``ChatService.run_turn`` y arma la
    respuesta wire ``ChatHttpResponse``. actions defensivas (decision #4): se descartan
    las malformadas, no se filtra basura al cliente.

    Rate-limit (S4, P1 seguridad): bucket por ``user_id`` (del JWT ya autenticado), ANTES
    de tocar la DB. fail-open si Redis cae. 429 con ``Retry-After`` (mismo shape que
    ``auth.py``) si se cruza el techo de la ventana.

    Returns:
        ``ChatHttpResponse`` con el texto final, las ``actions`` ejecutadas (validadas),
        el ``session_id`` (UUID de la ``ChatSession``) y el ``finish_reason`` del router.
    """
    if not await check_chat_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().chat_window_seconds)
    chat_session = await resolve_chat_session(
        session, user_id=user_id, session_id=body.session_id, mode=body.mode
    )
    service = ChatService(
        session, user_id, llm_client=llm_client, embedder=embedder, reranker=reranker
    )
    resp = await service.run_turn(chat_session, body)
    # Cargar la presión de escrituras de tools al bucket del chat (amplificación de
    # escritura): cada action ejecutada suma 1 punto extra a la ventana del usuario, así un
    # turno que dispara muchas tools agota la ventana antes. Post-turno y best-effort: NO
    # rechaza ESTE turno (ya pasó el gate); afecta los siguientes.
    await charge_chat_tool_writes(store, user_id=str(user_id), writes=len(resp.actions))
    return ChatHttpResponse(
        text=resp.text,
        actions=_to_http_actions(resp.actions),
        session_id=chat_session.id,
        finish_reason=resp.finish_reason,
    )


def _sse_event(name: str, payload: dict[str, Any]) -> str:
    """Serializa un evento SSE con nombre al wire que consume ``sse.ts``.

    Formato: ``event: <name>\\ndata: <json>\\n\\n``. El ``data`` SIEMPRE pasa por
    ``json.dumps(ensure_ascii=False)``: un ``'\\n'`` crudo dentro del payload partiria el
    bloque SSE (el separador de bloques es ``'\\n\\n'``), asi que nunca se interpola texto
    crudo. El doble ``'\\n\\n'`` final cierra el bloque.
    """
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def chat_stream(
    body: ChatHttpRequest,
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
    llm_client: LlmClientDep,
    embedder: EmbedderDep,
    reranker: RerankerDep,
) -> StreamingResponse:
    """Re-emite el turno de chat como stream SSE con eventos con nombre.

    Mismo contrato de turno que ``/chat`` (mismo ``ChatService.run_turn``); la diferencia
    es el wire: en vez de un JSON ``ChatHttpResponse``, emite el stream SSE que consume
    ``packages/shared-schemas/src/sse.ts``::

        event: token
        data: {"delta": "Hola"}

        event: done
        data: {"session_id": "...", "actions": [...], "finish_reason": "stop"}

    Diseno (NO re-litigar):

    (1) Orden: TODO el trabajo transaccional (DB + commit, en ``run_turn``) ocurre ANTES
        de construir el ``StreamingResponse``. Si algo falla aca (incluido el ``commit``),
        la excepcion propaga ANTES de devolver la response -> ``get_db()`` hace rollback
        -> 500 limpio con 0 bytes SSE (el stream nunca arranco). Los errores de validacion
        / auth / sesion (422 / 401 / 404 / 409) saltan aca como HTTP normales, NO como
        eventos SSE: el cliente los ve como status codes, no como ``event: error``.

    (2) Snapshot de primitivos ANTES del generator. El closure del generator cierra SOLO
        sobre ``str`` / ``list[dict]`` ya serializados; NUNCA sobre ``chat_session`` ni
        atributos ORM. Despues del ``commit`` un acceso lazy a un atributo ORM podria
        disparar I/O sobre una sesion ya cerrada (lazy-load post-commit). Snapshotear los
        primitivos lo evita de raiz.

    (3) ``StreamingResponse`` EXPLICITO, no un endpoint async-gen ni ``EventSourceResponse``.
        NO convertir esto a SSE nativo de FastAPI: a partir de 0.136 FastAPI tiene su propio
        soporte SSE que cambiaria tanto el wire (formato de los eventos) como el lifecycle
        (cuando corre el generator vs cuando se cierra la sesion DB). Devolver el
        ``StreamingResponse`` a mano fija el contrato exacto que ``sse.ts`` espera; un
        refactor futuro NO debe 'modernizarlo'.

    Returns:
        ``StreamingResponse`` ``text/event-stream`` que emite N eventos ``token`` (ventanas
        de ``_TOKEN_CHUNK_SIZE`` code-points del texto) seguidos de un evento ``done``. Si
        el texto es vacio: 0 tokens + 1 done.
    """
    # (0) Rate-limit por user_id (S4, P1 seguridad), ANTES de tocar la DB: el 429 salta como
    #     HTTP normal (no como event: error SSE), igual que 401/404/409. fail-open si Redis
    #     cae. Mismo bucket que /chat.
    if not await check_chat_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().chat_window_seconds)

    # (1) Resolver la sesion + mismo trabajo transaccional que /chat (en run_turn). Si algo
    #     falla aca (incl. commit) propaga ANTES del StreamingResponse -> get_db rollback ->
    #     500 limpio, 0 bytes SSE. 422/401/404/409 saltan aca como HTTP normales.
    chat_session = await resolve_chat_session(
        session, user_id=user_id, session_id=body.session_id, mode=body.mode
    )
    service = ChatService(
        session, user_id, llm_client=llm_client, embedder=embedder, reranker=reranker
    )
    resp = await service.run_turn(chat_session, body)

    # Cargar la presión de escrituras de tools al bucket del chat (misma amplificación que
    # /chat): cada action ejecutada suma 1 punto extra a la ventana. Post-turno, best-effort.
    await charge_chat_tool_writes(store, user_id=str(user_id), writes=len(resp.actions))

    # (2) SNAPSHOT de primitivos puros ANTES del generator. NUNCA se pasa chat_session ni
    #     atributos ORM al closure (evita lazy-load post-commit).
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

    # (3) Generator: cierra SOLO sobre str / list[dict] ya serializados. El try/except es una
    #     red de seguridad (regla #4, sin PII); en la practica improbable porque todo el
    #     payload esta pre-serializado.
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

    # (4) RETORNAR StreamingResponse explicito (NO async-gen endpoint, NO EventSourceResponse):
    #     fija el wire + lifecycle que espera sse.ts.
    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
