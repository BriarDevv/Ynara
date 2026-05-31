"""Tests de INTEGRACIÓN de la capa de memoria sagrada (M7, ADR-010).

Corren contra el pgvector REAL vía ``db_session`` (rollback al final de cada
test — no persisten nada entre tests). Requieren ``TEST_DATABASE_URL`` seteada
y el marker ``-m integration``.

Invariantes cubiertos (regla #3 / ADR-010):

1. ``test_semantic_roundtrip_encrypted``  — ``content`` en DB es ``BYTEA``
   (nunca el plaintext); search devuelve ``SemanticMemoryOut.content`` descifrado.
2. ``test_semantic_search_returns_user_rows_decrypted``  — search devuelve solo
   filas del user con ``content`` descifrado.
3. ``test_user_id_isolation``  — search/update/delete de user A nunca
   afecta/devuelve filas de user B; descifrar blob ajeno tira ``InvalidTag``.
4. ``test_episodic_roundtrip_encrypted``  — ``summary`` en DB es ``BYTEA``;
   search devuelve ``EpisodicMemoryOut.summary`` descifrado.
5. ``test_episodic_sensitive_retention_db_constraint``  — INSERT directo ORM con
   ``is_sensitive=True + retention_days=400`` → ``IntegrityError``
   (CHECK ``retention_days_sensitive_cap``).
6. ``test_procedural_upsert_idempotent``  — upsert 2 veces mismo key → 1 fila,
   ``confidence=1.0``, ``stale=False``, ``last_reinforced_at`` avanzó.
7. ``test_procedural_isolation``  — get/list_all/delete de un user no ve filas
   del otro.

No se mockea ``AsyncSession`` (AGENTS.md §5). Se inyectan ``FakeEmbeddingClient``
y ``FakeReranker`` para los stores que los requieren. Para tests de similaridad,
los vectores se siembran **a mano** en lugar de depender del FakeEmbeddingClient
(SHA-256 produce vectores casi-ortogonales → ranking inestable).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from cryptography.exceptions import InvalidTag
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_for_user, encrypt_for_user
from app.enums import Mode
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.reranker import FakeReranker
from app.memory.episodic import EpisodicMemoryStore
from app.memory.procedural import ProceduralMemoryStore
from app.memory.semantic import SemanticMemoryStore
from app.models.memory import EpisodicMemory, SemanticMemory
from app.models.session import ChatSession
from app.models.user import User
from app.schemas.memory import (
    EpisodicMemoryCreate,
    EpisodicMemoryOut,
    ProceduralMemoryUpsert,
    SemanticMemoryCreate,
    SemanticMemoryOut,
)

# ---------------------------------------------------------------------------
# Helpers de siembra
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(tz=UTC)


async def _seed_user(session: AsyncSession) -> User:
    """Inserta un User mínimo y lo retorna (flush, no commit — rollback al final)."""
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_session(session: AsyncSession, user: User) -> ChatSession:
    """Inserta una ChatSession válida para el user."""
    chat = ChatSession(user_id=user.id, mode=Mode.PRODUCTIVIDAD)
    session.add(chat)
    await session.flush()
    await session.refresh(chat)
    return chat


def _fake_stores(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> tuple[SemanticMemoryStore, EpisodicMemoryStore, ProceduralMemoryStore]:
    embedder = FakeEmbeddingClient()
    reranker = FakeReranker()
    semantic = SemanticMemoryStore(session, user_id, embedder, reranker)
    episodic = EpisodicMemoryStore(session, user_id, embedder, reranker)
    procedural = ProceduralMemoryStore(session, user_id)
    return semantic, episodic, procedural


# ---------------------------------------------------------------------------
# 1. Semantic — round-trip cifrado
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_semantic_roundtrip_encrypted(db_session: AsyncSession) -> None:
    """``content`` en la DB vive como BYTEA (cifrado); el Out lo devuelve descifrado.

    Pasos:
    1. add() un hecho → guarda el blob cifrado en la DB.
    2. Query cruda (ORM) sobre la columna ``content`` del row → assert es ``bytes``
       y no contiene el plaintext.
    3. search() → ``SemanticMemoryOut.content`` == plaintext original.
    """
    user = await _seed_user(db_session)
    semantic, _, _ = _fake_stores(db_session, user.id)

    plaintext = "el usuario prefiere voseo rioplatense"
    out = await semantic.add(SemanticMemoryCreate(content=plaintext))

    # El Out ya viene descifrado.
    assert isinstance(out, SemanticMemoryOut)
    assert out.content == plaintext

    # Query cruda: el blob guardado en la tabla debe ser bytes, no el texto.
    stmt = select(SemanticMemory.content).where(SemanticMemory.id == out.id)
    raw_blob: bytes = (await db_session.execute(stmt)).scalar_one()

    assert isinstance(raw_blob, bytes), "content en DB debe ser BYTEA"
    assert plaintext.encode() not in raw_blob, (
        "el plaintext NO debe aparecer en claro dentro del BYTEA"
    )

    # El search descifra correctamente.
    results = await semantic.search("voseo rioplatense", limit=5)
    found = next((r for r in results if r.id == out.id), None)
    assert found is not None, "search debe devolver el hecho recién insertado"
    assert found.content == plaintext


# ---------------------------------------------------------------------------
# 2. Semantic — search devuelve filas descifradas del user correcto
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_semantic_search_returns_user_rows_decrypted(db_session: AsyncSession) -> None:
    """search() devuelve solo filas del user del store, con content descifrado."""
    user = await _seed_user(db_session)
    semantic, _, _ = _fake_stores(db_session, user.id)

    facts = [
        "me gusta el mate amargo",
        "trabajo en software",
        "prefiero meetings cortas",
    ]
    outs = [await semantic.add(SemanticMemoryCreate(content=f)) for f in facts]
    ids_added = {o.id for o in outs}

    results = await semantic.search("trabajo y productividad", limit=5)

    # Todos los resultados son strings (no bytes).
    for r in results:
        assert isinstance(r.content, str), "content debe ser str, no bytes"
        assert r.user_id == user.id, "search no debe devolver filas de otros users"

    # Al menos las filas que insertamos deben estar.
    # No exigimos que las 3 aparezcan (limit y ANN pueden variar), pero sí que
    # todas las que aparecen correspondan a este user y estén en el set sembrado.
    for r in results:
        assert r.id in ids_added, "search devolvió un id que no insertamos en este test"


# ---------------------------------------------------------------------------
# 3. Aislamiento por user_id (semantic)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_user_id_isolation(db_session: AsyncSession) -> None:
    """search / update / delete de user A no ven ni afectan filas de user B."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)

    store_a, _, _ = _fake_stores(db_session, user_a.id)
    store_b, _, _ = _fake_stores(db_session, user_b.id)

    # User B inserta un hecho.
    out_b = await store_b.add(SemanticMemoryCreate(content="secreto de user B"))

    # User A busca: no debe ver filas de B.
    results_a = await store_a.search("secreto", limit=10)
    ids_a = {r.id for r in results_a}
    assert out_b.id not in ids_a, "user A no debe ver filas de user B"

    # User A intenta update sobre el id de B → None (no existe para A).
    updated = await store_a.update(out_b.id, "contenido manipulado")
    assert updated is None, "update cross-user debe devolver None"

    # User A intenta delete sobre el id de B → False.
    deleted = await store_a.delete(out_b.id)
    assert deleted is False, "delete cross-user debe devolver False"

    # El hecho de B sigue intacto (lo puede encontrar store_b).
    results_b = await store_b.search("secreto", limit=10)
    assert any(r.id == out_b.id for r in results_b), "la fila de B debe seguir existiendo"

    # Defensa extra: descifrar el blob de B con la key de A lanza InvalidTag.
    stmt = select(SemanticMemory.content).where(SemanticMemory.id == out_b.id)
    blob_b: bytes = (await db_session.execute(stmt)).scalar_one()
    with pytest.raises(InvalidTag):
        decrypt_for_user(user_a.id, blob_b)


# ---------------------------------------------------------------------------
# 3b. Semantic — update round-trip (re-embed + re-cifra)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_semantic_update_roundtrip(db_session: AsyncSession) -> None:
    """update() re-embeddea + re-cifra: el search posterior trae el contenido nuevo.

    Cierra el happy-path del update sobre la tabla sagrada: que el blob nuevo
    descifre al contenido actualizado (no al viejo) y que la búsqueda lo refleje.
    """
    user = await _seed_user(db_session)
    semantic, _, _ = _fake_stores(db_session, user.id)

    out = await semantic.add(SemanticMemoryCreate(content="el usuario vive en Córdoba"))

    updated = await semantic.update(out.id, "el usuario vive en Buenos Aires")
    assert updated is not None
    assert updated.id == out.id
    assert updated.content == "el usuario vive en Buenos Aires"

    # El blob persistido es el nuevo cifrado: descifra al contenido actualizado.
    stmt = select(SemanticMemory.content).where(SemanticMemory.id == out.id)
    raw_blob: bytes = (await db_session.execute(stmt)).scalar_one()
    assert isinstance(raw_blob, bytes)
    assert decrypt_for_user(user.id, raw_blob) == "el usuario vive en Buenos Aires"
    assert b"Buenos Aires" not in raw_blob, "el contenido nuevo tampoco va en claro"

    # El search posterior devuelve el contenido actualizado, no el original.
    results = await semantic.search("dónde vive", limit=5)
    found = next((r for r in results if r.id == out.id), None)
    assert found is not None
    assert found.content == "el usuario vive en Buenos Aires"


# ---------------------------------------------------------------------------
# 4. Episodic — round-trip cifrado
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_episodic_roundtrip_encrypted(db_session: AsyncSession) -> None:
    """``summary`` en DB es BYTEA; search devuelve ``EpisodicMemoryOut.summary`` descifrado."""
    user = await _seed_user(db_session)
    chat = await _seed_session(db_session, user)
    _, episodic, _ = _fake_stores(db_session, user.id)

    summary_text = "Sesión productiva: terminamos el sprint sin deuda técnica"
    payload = EpisodicMemoryCreate(
        session_id=chat.id,
        summary=summary_text,
        occurred_at=_now(),
        is_sensitive=False,
        retention_days=90,
        topics={"proyecto": "ynara"},
    )
    out = await episodic.add(payload)

    assert isinstance(out, EpisodicMemoryOut)
    assert out.summary == summary_text

    # Query cruda: BYTEA cifrado.
    stmt = select(EpisodicMemory.summary).where(EpisodicMemory.id == out.id)
    raw_blob: bytes = (await db_session.execute(stmt)).scalar_one()
    assert isinstance(raw_blob, bytes), "summary en DB debe ser BYTEA"
    assert summary_text.encode() not in raw_blob, (
        "el plaintext NO debe aparecer en claro dentro del BYTEA"
    )

    # search descifra correctamente.
    results = await episodic.search("sprint deuda técnica", limit=5)
    found = next((r for r in results if r.id == out.id), None)
    assert found is not None, "search debe devolver el episodio recién insertado"
    assert found.summary == summary_text
    assert found.topics == {"proyecto": "ynara"}
    assert found.is_sensitive is False
    assert found.retention_days == 90


# ---------------------------------------------------------------------------
# 5. Episodic — CHECK retention_days_sensitive_cap en DB
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_episodic_sensitive_retention_db_constraint(db_session: AsyncSession) -> None:
    """INSERT ORM con is_sensitive=True + retention_days=400 → IntegrityError.

    Bypasea la validación Pydantic (que ya captura esto antes) para verificar
    que la CHECK constraint ``retention_days_sensitive_cap`` existe y funciona
    en la DB real.
    """
    user = await _seed_user(db_session)
    chat = await _seed_session(db_session, user)

    embedder = FakeEmbeddingClient()
    embedding = (await embedder.embed(["test"]))[0]
    blob = encrypt_for_user(user.id, "contenido sensible")

    row = EpisodicMemory(
        user_id=user.id,
        session_id=chat.id,
        summary=blob,
        summary_embedding=embedding,
        is_sensitive=True,
        retention_days=400,  # viola la CHECK
        occurred_at=_now(),
        topics={},
    )
    db_session.add(row)

    with pytest.raises(IntegrityError):
        await db_session.flush()

    # Rollback explícito para dejar la sesión en estado limpio tras la excepción.
    await db_session.rollback()


# ---------------------------------------------------------------------------
# 6. Procedural — upsert idempotente
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_procedural_upsert_idempotent(db_session: AsyncSession) -> None:
    """Upsert del mismo key 2 veces → 1 sola fila con confidence=1.0, stale=False.

    El segundo upsert debe actualizar ``last_reinforced_at`` (ADR-007 D1: reforzar
    resetea el decay). Se verifica que ``last_reinforced_at`` del segundo upsert
    es >= al del primero (nunca retrocede).
    """
    user = await _seed_user(db_session)
    _, _, procedural = _fake_stores(db_session, user.id)

    payload_v1 = ProceduralMemoryUpsert(key="preferencia.idioma", value={"idioma": "es"})
    out1 = await procedural.upsert(payload_v1)

    reinforced_at_1 = out1.last_reinforced_at

    payload_v2 = ProceduralMemoryUpsert(
        key="preferencia.idioma", value={"idioma": "es-rioplatense"}
    )
    out2 = await procedural.upsert(payload_v2)

    # Sigue siendo 1 sola fila.
    all_entries = await procedural.list_all()
    matching = [e for e in all_entries if e.key == "preferencia.idioma"]
    assert len(matching) == 1, "upsert del mismo key debe dejar 1 sola fila"

    # El valor se actualizó.
    assert out2.value == {"idioma": "es-rioplatense"}

    # Decay reseteado.
    assert out2.confidence == 1.0
    assert out2.stale is False

    # last_reinforced_at no retrocedió (puede ser igual si el clock no avanzó).
    assert out2.last_reinforced_at >= reinforced_at_1

    # El id es el mismo (misma fila).
    assert out2.id == out1.id


# ---------------------------------------------------------------------------
# 7. Procedural — aislamiento + get / list_all / delete
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_procedural_isolation(db_session: AsyncSession) -> None:
    """get / list_all / delete de user A no ven ni afectan entradas de user B."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)

    _, _, proc_a = _fake_stores(db_session, user_a.id)
    _, _, proc_b = _fake_stores(db_session, user_b.id)

    # Cada user inserta una entrada con la misma key.
    await proc_a.upsert(ProceduralMemoryUpsert(key="tema.favorito", value={"tema": "código"}))
    await proc_b.upsert(ProceduralMemoryUpsert(key="tema.favorito", value={"tema": "diseño"}))

    # get: cada store ve solo su propia entrada.
    entry_a = await proc_a.get("tema.favorito")
    entry_b = await proc_b.get("tema.favorito")
    assert entry_a is not None
    assert entry_b is not None
    assert entry_a.value == {"tema": "código"}
    assert entry_b.value == {"tema": "diseño"}
    assert entry_a.user_id == user_a.id
    assert entry_b.user_id == user_b.id

    # list_all: user A solo lista sus entradas.
    list_a = await proc_a.list_all()
    assert all(e.user_id == user_a.id for e in list_a)
    assert not any(e.user_id == user_b.id for e in list_a)

    # delete: user A borra su propia entrada → True; intento en key de B → False.
    deleted_own = await proc_a.delete("tema.favorito")
    assert deleted_own is True

    # Después del borrado, A ya no la ve.
    assert await proc_a.get("tema.favorito") is None

    # B sigue viendo la suya intacta.
    entry_b_after = await proc_b.get("tema.favorito")
    assert entry_b_after is not None
    assert entry_b_after.value == {"tema": "diseño"}


# ---------------------------------------------------------------------------
# 8. Read-only Ola 1 — list_all / count / get_by_id (semantic & episodic)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_semantic_list_all_and_count_paginate_decrypted(db_session: AsyncSession) -> None:
    """list_all() pagina (created_at DESC) y descifra; count() es el total del user."""
    user = await _seed_user(db_session)
    semantic, _, _ = _fake_stores(db_session, user.id)

    for i in range(3):
        await semantic.add(SemanticMemoryCreate(content=f"hecho {i}"))

    # count() = total del user.
    assert await semantic.count() == 3

    # Página de 2: items descifrados (str), todos del user.
    page = await semantic.list_all(limit=2, offset=0)
    assert len(page) == 2
    for item in page:
        assert isinstance(item.content, str)
        assert item.content.startswith("hecho ")
        assert item.user_id == user.id

    # offset trae el resto sin solapar.
    rest = await semantic.list_all(limit=2, offset=2)
    assert len(rest) == 1
    assert {i.id for i in page}.isdisjoint({i.id for i in rest})


@pytest.mark.integration
async def test_semantic_get_by_id_decrypt_post_ownership(db_session: AsyncSession) -> None:
    """get_by_id: propio → Out descifrado; ajeno/inexistente → None SIN descifrar.

    Es la disciplina SAGRADA decrypt-post-ownership: pedir el id de B desde el store
    de A devuelve None (filtro user_id antes de crypto), NUNCA intenta descifrar el
    blob de B con la key de A (eso tiraría InvalidTag; ni se llega ahí).
    """
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    store_a, _, _ = _fake_stores(db_session, user_a.id)
    store_b, _, _ = _fake_stores(db_session, user_b.id)

    out_a = await store_a.add(SemanticMemoryCreate(content="hecho propio de A"))
    out_b = await store_b.add(SemanticMemoryCreate(content="hecho de B"))

    # Propio: descifra y devuelve el Out.
    got = await store_a.get_by_id(out_a.id)
    assert got is not None
    assert got.content == "hecho propio de A"
    assert got.user_id == user_a.id

    # Ajeno: None (sin intentar descifrar el blob de B con la key de A).
    assert await store_a.get_by_id(out_b.id) is None

    # Inexistente: None.
    assert await store_a.get_by_id(uuid.uuid4()) is None


@pytest.mark.integration
async def test_episodic_list_all_and_get_by_id_post_ownership(db_session: AsyncSession) -> None:
    """Episodic: list_all/count descifran summary; get_by_id ajeno → None sin crypto."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    chat_a = await _seed_session(db_session, user_a)
    chat_b = await _seed_session(db_session, user_b)
    _, epi_a, _ = _fake_stores(db_session, user_a.id)
    _, epi_b, _ = _fake_stores(db_session, user_b.id)

    out_a = await epi_a.add(
        EpisodicMemoryCreate(
            session_id=chat_a.id,
            summary="episodio de A",
            occurred_at=_now(),
            retention_days=90,
        )
    )
    out_b = await epi_b.add(
        EpisodicMemoryCreate(
            session_id=chat_b.id,
            summary="episodio de B",
            occurred_at=_now(),
            retention_days=90,
        )
    )

    # list_all + count del user A: solo su episodio, summary descifrado.
    assert await epi_a.count() == 1
    page = await epi_a.list_all(limit=50, offset=0)
    assert len(page) == 1
    assert page[0].summary == "episodio de A"
    assert page[0].user_id == user_a.id

    # get_by_id propio descifra; ajeno e inexistente → None sin tocar crypto.
    got = await epi_a.get_by_id(out_a.id)
    assert got is not None
    assert got.summary == "episodio de A"
    assert await epi_a.get_by_id(out_b.id) is None
    assert await epi_a.get_by_id(uuid.uuid4()) is None
