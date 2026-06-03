"""Tests de INTEGRACIÓN: las mutaciones de memoria por ENDPOINT auditan en ``audit_log`` (#161).

Complementan ``tests/integration/test_audit_writes.py`` (que cubre la sede de la
CONSOLIDACIÓN — ``apply_ops`` con ``origin_model=QWEN``): acá se cubre la sede del
ENDPOINT HTTP (``app/api/v1/memory.py``), donde el DUEÑO muta su propia memoria con
su JWT y cada PATCH/DELETE/wipe EFECTIVO deja su fila de auditoría con
``origin_model=None`` (acción del usuario por HTTP, sin LLM).

Setup espejado EXACTO de ``tests/api/test_memory.py`` (``httpx.AsyncClient`` +
``ASGITransport(app=app)``, override de ``get_db`` con el ``db_session`` del fixture,
Fakes inyectados, JWT del user vía ``create_access_token``) y el patrón de assert de
``tests/integration/test_audit_writes.py`` (query a ``AuditLog`` filtrando por
``user_id``). Los endpoints mutantes commitean: como el ``db_session`` corre en un
savepoint (``join_transaction_mode="create_savepoint"``), ese commit commitea el
SAVEPOINT —no la transacción externa— así que las filas de audit quedan consultables
en la MISMA sesión y el rollback final del fixture limpia.

REGLA #4: ningún assert toca contenido del usuario; solo metadata + ``record_hash``
(sha256 hex) computado con los helpers canónicos del impl (``_record_hash`` /
``_procedural_hash_payload``). Los caminos que NO mutan (404 / 422 / 409) NO auditan.

Cobertura (cada caso consulta ``audit_log`` tras la llamada al endpoint):
1. PATCH semantic OK   -> 1 fila UPDATE/SEMANTIC, target_id = id, hash = _record_hash(content).
2. PATCH procedural OK -> 1 fila UPDATE/PROCEDURAL, hash = _record_hash(payload canónico).
3. DELETE semantic OK  -> 1 fila DELETE/SEMANTIC, target_id = UUID borrado.
4. DELETE episodic OK  -> 1 fila DELETE/EPISODIC, sensitive=True conservador (sin descifrar).
5. DELETE procedural OK -> 1 fila DELETE/PROCEDURAL, target_id is None.
6. POST /memory/wipe execute -> 1 fila DELETE por capa con datos, target_id None, hash wipe:<capa>.
7. NO-mutación: 404 / 422 / 409 -> 0 filas nuevas en audit_log.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_embedder, get_reranker
from app.core.security import create_access_token
from app.enums import AuditOperation, MemoryLayer, Mode
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.reranker import FakeReranker
from app.llm.memory_engine import _procedural_hash_payload, _record_hash
from app.main import app
from app.memory.episodic import EpisodicMemoryStore
from app.memory.procedural import ProceduralMemoryStore
from app.memory.semantic import SemanticMemoryStore
from app.models.audit import AuditLog
from app.models.session import ChatSession
from app.models.user import User
from app.schemas.memory import (
    EpisodicMemoryCreate,
    ProceduralMemoryUpsert,
    SemanticMemoryCreate,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers de siembra (flush, NO commit — el rollback del fixture limpia)
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession) -> User:
    """Inserta un User mínimo y hace flush para que tenga id asignado.

    La FK ``audit_log.user_id`` -> ``users.id`` requiere un user real en la DB.
    """
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_chat_session(session: AsyncSession, user_id: uuid.UUID) -> ChatSession:
    """Inserta una ChatSession (FK que la episódica necesita en session_id)."""
    cs = ChatSession(user_id=user_id, mode=Mode.PRODUCTIVIDAD)
    session.add(cs)
    await session.flush()
    await session.refresh(cs)
    return cs


def _stores(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[SemanticMemoryStore, EpisodicMemoryStore, ProceduralMemoryStore]:
    embedder = FakeEmbeddingClient()
    reranker = FakeReranker()
    return (
        SemanticMemoryStore(session, user_id, embedder, reranker),
        EpisodicMemoryStore(session, user_id, embedder, reranker),
        ProceduralMemoryStore(session, user_id),
    )


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    """Header Authorization con un JWT válido para ``user_id``."""
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession) -> httpx.AsyncClient:
    """Overridea ``get_db`` + clientes Fake y devuelve el cliente ASGI.

    Espejo de ``tests/api/test_memory.py``: el caller usa el cliente dentro de
    ``async with`` y limpia los overrides en su ``finally`` con
    ``app.dependency_overrides.clear()``. Los Fake se overridean porque el lifespan
    (que los pone en ``app.state``) no corre bajo ``ASGITransport`` sin startup.
    """

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_embedder] = lambda: FakeEmbeddingClient()
    app.dependency_overrides[get_reranker] = lambda: FakeReranker()
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _audit_rows(session: AsyncSession, user_id: uuid.UUID) -> list[AuditLog]:
    """Trae TODAS las filas de ``audit_log`` del user, ordenadas por ``created_at``."""
    stmt = select(AuditLog).where(AuditLog.user_id == user_id).order_by(AuditLog.created_at)
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# 1. PATCH semantic OK -> 1 fila UPDATE/SEMANTIC (target_id, hash, origin_model None)
# ---------------------------------------------------------------------------


async def test_patch_semantic_writes_audit_update(db_session: AsyncSession) -> None:
    """PATCH semantic propio -> 1 fila UPDATE/SEMANTIC, target_id = id, hash del content nuevo."""
    user = await _seed_user(db_session)
    semantic, _, _ = _stores(db_session, user.id)
    item = await semantic.add(SemanticMemoryCreate(content="dato original"))
    await db_session.flush()

    new_content = "dato corregido por el dueño"
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/memory/semantic/{item.id}",
                json={"content": new_content},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 200

        rows = await _audit_rows(db_session, user.id)
        assert len(rows) == 1
        row = rows[0]
        assert row.operation == AuditOperation.UPDATE
        assert row.target_layer == MemoryLayer.SEMANTIC
        assert row.target_id == item.id
        assert row.record_hash == _record_hash(new_content)
        assert row.sensitive is False
        # Acción del usuario por HTTP: sin LLM/tool (distingue del audit de consolidación).
        assert row.origin_model is None
        assert row.origin_mode is None
        assert row.origin_tool is None
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. PATCH procedural OK -> 1 fila UPDATE/PROCEDURAL (hash del payload canónico)
# ---------------------------------------------------------------------------


async def test_patch_procedural_writes_audit_update(db_session: AsyncSession) -> None:
    """PATCH procedural propio -> 1 fila UPDATE/PROCEDURAL; hash del payload canónico."""
    user = await _seed_user(db_session)
    _, _, procedural = _stores(db_session, user.id)
    entry = await procedural.upsert(ProceduralMemoryUpsert(key="tono", value={"tono": "formal"}))
    await db_session.flush()

    new_value = {"tono": "informal", "n": 7}
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/memory/procedural/{entry.key}",
                json={"value": new_value},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 200

        rows = await _audit_rows(db_session, user.id)
        assert len(rows) == 1
        row = rows[0]
        assert row.operation == AuditOperation.UPDATE
        assert row.target_layer == MemoryLayer.PROCEDURAL
        assert row.target_id == entry.id
        assert row.record_hash == _record_hash(_procedural_hash_payload(entry.key, new_value))
        assert row.sensitive is False
        assert row.origin_model is None
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. DELETE semantic OK -> 1 fila DELETE/SEMANTIC (target_id = UUID borrado)
# ---------------------------------------------------------------------------


async def test_delete_semantic_writes_audit_delete(db_session: AsyncSession) -> None:
    """DELETE semantic propio -> 1 fila DELETE/SEMANTIC, target_id = UUID, hash = sha256(id)."""
    user = await _seed_user(db_session)
    semantic, _, _ = _stores(db_session, user.id)
    item = await semantic.add(SemanticMemoryCreate(content="hecho a borrar"))
    await db_session.flush()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.delete(f"/v1/memory/semantic/{item.id}", headers=_bearer(user.id))
        assert resp.status_code == 204

        rows = await _audit_rows(db_session, user.id)
        assert len(rows) == 1
        row = rows[0]
        assert row.operation == AuditOperation.DELETE
        assert row.target_layer == MemoryLayer.SEMANTIC
        assert row.target_id == item.id
        assert row.record_hash == _record_hash(str(item.id))
        assert row.sensitive is False
        assert row.origin_model is None
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. DELETE episodic OK -> 1 fila DELETE/EPISODIC (sensitive=True conservador)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seeded_sensitive", [True, False])
async def test_delete_episodic_writes_audit_delete_sensitive(
    db_session: AsyncSession, seeded_sensitive: bool
) -> None:
    """DELETE episodic -> 1 fila DELETE/EPISODIC con ``sensitive=True`` conservador.

    El audit marca ``sensitive=True`` para TODA op episódica (la única capa con contenido
    sensible) SIN descifrar la entrada para leer ``is_sensitive`` — sobre-marcar es fail-safe
    y evita ampliar la superficie de descifrado sobre la capa sensible. El parametrize
    confirma que el resultado es ``True`` sin importar el ``is_sensitive`` REAL de la entrada.
    """
    user = await _seed_user(db_session)
    cs = await _seed_chat_session(db_session, user.id)
    _, episodic, _ = _stores(db_session, user.id)
    epi = await episodic.add(
        EpisodicMemoryCreate(
            session_id=cs.id,
            summary="resumen episodico a borrar",
            occurred_at=cs.started_at,
            is_sensitive=seeded_sensitive,
            retention_days=90,
            topics={"k": "v"},
        )
    )
    await db_session.flush()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.delete(f"/v1/memory/episodic/{epi.id}", headers=_bearer(user.id))
        assert resp.status_code == 204

        rows = await _audit_rows(db_session, user.id)
        assert len(rows) == 1
        row = rows[0]
        assert row.operation == AuditOperation.DELETE
        assert row.target_layer == MemoryLayer.EPISODIC
        assert row.target_id == epi.id
        assert row.record_hash == _record_hash(str(epi.id))
        # Conservador: episódica -> sensitive=True SIEMPRE, sin descifrar para leer is_sensitive.
        assert row.sensitive is True
        assert row.origin_model is None
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. DELETE procedural OK -> 1 fila DELETE/PROCEDURAL (target_id is None)
# ---------------------------------------------------------------------------


async def test_delete_procedural_writes_audit_null_target(db_session: AsyncSession) -> None:
    """DELETE procedural -> 1 fila DELETE/PROCEDURAL, target_id is None, hash = sha256(key)."""
    user = await _seed_user(db_session)
    _, _, procedural = _stores(db_session, user.id)
    entry = await procedural.upsert(ProceduralMemoryUpsert(key="pref.borrar", value={"x": 1}))
    await db_session.flush()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.delete(
                f"/v1/memory/procedural/{entry.key}", headers=_bearer(user.id)
            )
        assert resp.status_code == 204

        rows = await _audit_rows(db_session, user.id)
        assert len(rows) == 1
        row = rows[0]
        assert row.operation == AuditOperation.DELETE
        assert row.target_layer == MemoryLayer.PROCEDURAL
        # El delete-by-key no retorna id: target_id NULL, el hash de la key ata la fila.
        assert row.target_id is None
        assert row.record_hash == _record_hash(entry.key)
        assert row.sensitive is False
        assert row.origin_model is None
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. POST /memory/wipe execute -> 1 fila DELETE por capa con datos (target_id None, hash wipe)
# ---------------------------------------------------------------------------


async def test_wipe_execute_writes_one_audit_row_per_layer(db_session: AsyncSession) -> None:
    """Wipe con datos en las 3 capas -> 3 filas DELETE (una por capa), target_id None, hash wipe."""
    user = await _seed_user(db_session)
    cs = await _seed_chat_session(db_session, user.id)
    semantic, episodic, procedural = _stores(db_session, user.id)
    await semantic.add(SemanticMemoryCreate(content="hecho semantico"))
    await episodic.add(
        EpisodicMemoryCreate(
            session_id=cs.id,
            summary="resumen episodico",
            occurred_at=cs.started_at,
            is_sensitive=False,
            retention_days=90,
            topics={"k": "v"},
        )
    )
    await procedural.upsert(ProceduralMemoryUpsert(key="pref.x", value={"x": 1}))
    await db_session.flush()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/memory/wipe",
                json={
                    "expected_semantic": 1,
                    "expected_episodic": 1,
                    "expected_procedural": 1,
                },
                headers=_bearer(user.id),
            )
        assert resp.status_code == 200

        rows = await _audit_rows(db_session, user.id)
        # Una fila DELETE por capa con rowcount > 0 (las 3 tenían datos).
        assert len(rows) == 3
        assert all(row.operation == AuditOperation.DELETE for row in rows)
        assert all(row.target_id is None for row in rows)
        assert all(row.origin_model is None for row in rows)

        by_layer = {row.target_layer: row for row in rows}
        assert set(by_layer) == {
            MemoryLayer.SEMANTIC,
            MemoryLayer.EPISODIC,
            MemoryLayer.PROCEDURAL,
        }
        for layer, row in by_layer.items():
            assert row.record_hash == _record_hash(f"wipe:{layer.value}")
        # EPISODIC va sensitive=True conservador (el wipe masivo no lee is_sensitive per-entry).
        assert by_layer[MemoryLayer.EPISODIC].sensitive is True
        assert by_layer[MemoryLayer.SEMANTIC].sensitive is False
        assert by_layer[MemoryLayer.PROCEDURAL].sensitive is False
    finally:
        app.dependency_overrides.clear()


async def test_wipe_execute_skips_empty_layers_in_audit(db_session: AsyncSession) -> None:
    """Wipe con datos SOLO en semantic -> 1 fila DELETE/SEMANTIC (las capas vacías no auditan)."""
    user = await _seed_user(db_session)
    semantic, _, _ = _stores(db_session, user.id)
    await semantic.add(SemanticMemoryCreate(content="unico hecho"))
    await db_session.flush()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/memory/wipe",
                json={
                    "expected_semantic": 1,
                    "expected_episodic": 0,
                    "expected_procedural": 0,
                },
                headers=_bearer(user.id),
            )
        assert resp.status_code == 200

        rows = await _audit_rows(db_session, user.id)
        # Solo semantic tenía rowcount > 0: episodic/procedural (0 borrados) NO auditan.
        assert len(rows) == 1
        row = rows[0]
        assert row.operation == AuditOperation.DELETE
        assert row.target_layer == MemoryLayer.SEMANTIC
        assert row.target_id is None
        assert row.record_hash == _record_hash(f"wipe:{MemoryLayer.SEMANTIC.value}")
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 7. Caminos que NO mutan NO auditan: 404 / 422 / 409 -> 0 filas nuevas
# ---------------------------------------------------------------------------


async def test_patch_other_users_semantic_404_no_audit(db_session: AsyncSession) -> None:
    """PATCH del item semantic de OTRO user -> 404; el owner NO recibe ninguna fila de audit."""
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)
    semantic, _, _ = _stores(db_session, owner.id)
    item = await semantic.add(SemanticMemoryCreate(content="hecho del owner"))
    await db_session.flush()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/memory/semantic/{item.id}",
                json={"content": "inyectado"},
                headers=_bearer(intruder.id),
            )
        assert resp.status_code == 404

        # Ni el owner ni el intruder tienen filas de audit: el 404 no muta nada.
        assert await _audit_rows(db_session, owner.id) == []
        assert await _audit_rows(db_session, intruder.id) == []
    finally:
        app.dependency_overrides.clear()


async def test_delete_nonexistent_404_no_audit(db_session: AsyncSession) -> None:
    """DELETE de un id/key inexistente -> 404; 0 filas de audit (no se borró nada)."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            d_sem = await client.delete(
                f"/v1/memory/semantic/{uuid.uuid4()}", headers=_bearer(user.id)
            )
            d_proc = await client.delete(
                "/v1/memory/procedural/pref.no-existe", headers=_bearer(user.id)
            )
        assert d_sem.status_code == 404
        assert d_proc.status_code == 404

        assert await _audit_rows(db_session, user.id) == []
    finally:
        app.dependency_overrides.clear()


async def test_patch_invalid_body_422_no_audit(db_session: AsyncSession) -> None:
    """PATCH semantic sin 'content' -> 422 (body no aplica a la capa); 0 filas de audit."""
    user = await _seed_user(db_session)
    semantic, _, _ = _stores(db_session, user.id)
    item = await semantic.add(SemanticMemoryCreate(content="hecho"))
    await db_session.flush()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/memory/semantic/{item.id}",
                json={"value": {"x": 1}},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 422

        assert await _audit_rows(db_session, user.id) == []
    finally:
        app.dependency_overrides.clear()


async def test_wipe_confirm_mismatch_409_no_audit(db_session: AsyncSession) -> None:
    """Wipe con confirm que NO matchea -> 409 (nada borrado); 0 filas de audit."""
    user = await _seed_user(db_session)
    semantic, _, _ = _stores(db_session, user.id)
    await semantic.add(SemanticMemoryCreate(content="hecho que sobrevive"))
    await db_session.flush()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/memory/wipe",
                json={
                    # El user tiene semantic=1; mandamos un confirm que no matchea.
                    "expected_semantic": 5,
                    "expected_episodic": 0,
                    "expected_procedural": 0,
                },
                headers=_bearer(user.id),
            )
        assert resp.status_code == 409

        # 409 aborta ANTES del wipe: nada se borró, nada se auditó.
        assert await _audit_rows(db_session, user.id) == []
    finally:
        app.dependency_overrides.clear()
