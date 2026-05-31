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
    + user actual) en cada request; ningun turno se persiste todavia. El
    ``sessions.id`` es solo el ancla (FK futura para episodica /
    ``source_session_id``); M9 lo expone honesto sin sobre-vender memoria de
    conversacion. En M9 el worker de consolidacion NO usa ``session_id`` como FK
    al encolar, asi que no necesita la fila committeada antes del enqueue.

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

El trabajo transaccional de un turno (DB + router + commit) vive en
``_run_chat_turn``, helper extraido para compartirlo con el endpoint de
streaming (``POST /v1/chat/stream``, M9 Ola 3): ambos hacen EXACTAMENTE el mismo
turno y solo difieren en como serializan el resultado.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._sessions import resolve_chat_session
from app.core.deps import (
    CurrentUser,
    DbSession,
    get_embedder,
    get_llm_client,
    get_reranker,
)
from app.llm.clients.base import LLMClient
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.llm.router import route
from app.llm.schemas import ChatRequest, ChatResponse
from app.models.session import ChatSession
from app.schemas.chat import Action, ChatHttpRequest, ChatHttpResponse

router = APIRouter()


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

    Orden transaccional (decision #2 M9, byte-a-byte el del ``/chat`` original):
    ``resolve_chat_session`` (flush, sin commit) -> ``route()`` ->
    ``session.commit()`` DESPUES de ``route()``. Es seguro commitear al final
    porque ``route()`` nunca propaga errores del LLM (overflow / error
    permanente devuelven fallback); asi se evita persistir una ``ChatSession``
    huerfana y se mantiene el commit unico por request. Si saltara un bug
    inesperado antes del commit, ``get_db()`` hace rollback y nada se persiste.

    M9 NO entrega multi-turno: ``route()`` arma ``messages`` desde cero (system
    + user actual) en cada llamada; ningun turno se persiste. El ``session_id``
    es solo el ancla de la ``ChatSession`` (FK futura), no historial vivo.

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

    # (4) Commit AL FINAL, despues de route(): persiste la ChatSession (y lo que
    #     hayan escrito los stores en esta sesion). Si saltara un bug inesperado
    #     antes de aca, get_db() hace rollback y nada se persiste.
    await session.commit()

    return chat_session, resp


@router.post("/chat", response_model=ChatHttpResponse, status_code=200)
async def chat(
    body: ChatHttpRequest,
    session: DbSession,
    user_id: CurrentUser,
    llm_client: Annotated[LLMClient, Depends(get_llm_client)],
    embedder: Annotated[EmbeddingClient, Depends(get_embedder)],
    reranker: Annotated[Reranker, Depends(get_reranker)],
) -> ChatHttpResponse:
    """Procesa un turno de chat: resuelve la sesion, invoca el router y responde.

    Delega el trabajo transaccional (DB + router + commit) en ``_run_chat_turn``
    y arma la respuesta wire ``ChatHttpResponse``. actions defensivas
    (decision #4): se descartan las malformadas, no se filtra basura al cliente.

    Returns:
        ``ChatHttpResponse`` con el texto final, las ``actions`` ejecutadas
        (validadas), el ``session_id`` (UUID de la ``ChatSession``) y el
        ``finish_reason`` del router.
    """
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
