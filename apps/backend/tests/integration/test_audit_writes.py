"""Tests de INTEGRACIÓN de la ESCRITURA de ``audit_log`` (issue #158).

Cubren la sede de escritura real de la tabla sagrada ``audit_log``: cada op de
memoria APLICADA en ``apply_ops`` (con un ``AuditStore`` real) deja una fila de
auditoría, y la consolidación end-to-end (``_async_consolidate``) escribe N
filas para N ops.

Estos tests solo LEEN/insertan filas de ``audit_log`` vía el ``AuditStore`` y el
ORM — NUNCA modifican el modelo (``app/models/audit.py``) ni la migración
(regla #3). Corren contra el Postgres REAL vía ``db_session`` (savepoint +
rollback al final) y requieren ``TEST_DATABASE_URL`` + el marker ``integration``.

REGLA #4 (perímetro): la fila de ``audit_log`` NUNCA contiene texto del usuario;
solo metadata + ``record_hash`` (sha256 hex de 64 chars del contenido/identificador
afectado). Hay un test dedicado que asierta que el plaintext NO aparece en
ninguna columna de la fila.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.reranker import FakeReranker
from app.llm.memory_engine import FakeMemoryEngine, MemoryOp, apply_ops
from app.llm.schemas import CompletionResult
from app.memory.audit import AuditStore
from app.memory.procedural import ProceduralMemoryStore
from app.memory.semantic import SemanticMemoryStore
from app.models.audit import AuditLog
from app.models.memory import SemanticMemory
from app.models.session import ChatSession
from app.models.user import User
from app.schemas.memory import ProceduralMemoryUpsert, SemanticMemoryCreate
from app.workflows.consolidation import _async_consolidate

# ---------------------------------------------------------------------------
# Helpers de siembra / lectura
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession) -> User:
    """Inserta un User mínimo y lo retorna (flush, no commit — rollback al final).

    La FK ``audit_log.user_id`` -> ``users.id`` requiere un user real en la DB.
    """
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_session(session: AsyncSession, user_id: UUID, mode: Mode = Mode.VIDA) -> UUID:
    """Inserta una ``ChatSession`` real y devuelve su id.

    La FK ``semantic_memory.source_session_id`` -> ``sessions.id`` requiere una
    fila real en ``sessions`` para que el ADD semantic con provenance no viole el
    FK (M10 Ola 1). Flush sin commit: el rollback del fixture limpia al final.
    """
    chat_session = ChatSession(user_id=user_id, mode=mode)
    session.add(chat_session)
    await session.flush()
    await session.refresh(chat_session)
    return chat_session.id


def _make_stores(
    session: AsyncSession, user_id: UUID
) -> tuple[SemanticMemoryStore, ProceduralMemoryStore, AuditStore]:
    embedder = FakeEmbeddingClient()
    reranker = FakeReranker()
    semantic = SemanticMemoryStore(session, user_id, embedder, reranker)
    procedural = ProceduralMemoryStore(session, user_id)
    audit = AuditStore(session, user_id)
    return semantic, procedural, audit


async def _fetch_audit_rows(session: AsyncSession, user_id: UUID) -> list[AuditLog]:
    """Trae TODAS las filas de ``audit_log`` del user, ordenadas por ``created_at``."""
    stmt = select(AuditLog).where(AuditLog.user_id == user_id).order_by(AuditLog.created_at)
    return list((await session.execute(stmt)).scalars().all())


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _make_llm_with_ops(ops_json: str) -> FakeLlmClient:
    client = FakeLlmClient(served_models=frozenset({"qwen"}))
    client.queue_result(
        CompletionResult(
            text=ops_json,
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=20,
            model_name="qwen",
            latency_ms=5.0,
        )
    )
    return client


# ---------------------------------------------------------------------------
# 1. ADD semantic -> 1 fila write
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_apply_ops_add_semantic_writes_audit(db_session: AsyncSession) -> None:
    """ADD semantic -> 1 fila audit (write/semantic, target_id = id del hecho, hash = sha256)."""
    user = await _seed_user(db_session)
    semantic, procedural, audit = _make_stores(db_session, user.id)

    content = "El usuario trabaja como ingeniero."
    ops = [MemoryOp(op="ADD", layer="semantic", content=content)]
    applied = await apply_ops(
        ops,
        semantic_store=semantic,
        procedural_store=procedural,
        audit_store=audit,
        origin_model=LlmModel.QWEN,
        origin_mode=Mode.VIDA,
    )
    assert applied == 1

    rows = await _fetch_audit_rows(db_session, user.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.operation == AuditOperation.WRITE
    assert row.target_layer == MemoryLayer.SEMANTIC
    assert row.origin_model == LlmModel.QWEN
    assert row.origin_mode == Mode.VIDA
    assert row.sensitive is False
    assert row.record_hash == _sha256(content)
    assert row.target_id is not None

    # target_id apunta al hecho recién creado (la única fila semantic del user).
    stmt = select(SemanticMemory.id).where(SemanticMemory.user_id == user.id)
    fact_id = (await db_session.execute(stmt)).scalar_one()
    assert row.target_id == fact_id


# ---------------------------------------------------------------------------
# 2. UPDATE semantic -> 1 fila update
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_apply_ops_update_semantic_writes_audit(db_session: AsyncSession) -> None:
    """UPDATE semantic -> audit update/semantic con target_id == id del hecho actualizado."""
    user = await _seed_user(db_session)
    semantic, procedural, audit = _make_stores(db_session, user.id)

    # Sembramos el hecho directo via store para tener su id (sin auditar el ADD).
    created = await semantic.add(SemanticMemoryCreate(content="dato original"))

    new_content = "dato corregido"
    ops = [MemoryOp(op="UPDATE", layer="semantic", content=new_content, target_id=str(created.id))]
    applied = await apply_ops(
        ops,
        semantic_store=semantic,
        procedural_store=procedural,
        audit_store=audit,
        origin_model=LlmModel.QWEN,
        origin_mode=Mode.ESTUDIO,
    )
    assert applied == 1

    rows = await _fetch_audit_rows(db_session, user.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.operation == AuditOperation.UPDATE
    assert row.target_layer == MemoryLayer.SEMANTIC
    assert row.target_id == created.id
    assert row.record_hash == _sha256(new_content)
    assert row.origin_mode == Mode.ESTUDIO


# ---------------------------------------------------------------------------
# 3. DELETE semantic -> 1 fila delete
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_apply_ops_delete_semantic_writes_audit(db_session: AsyncSession) -> None:
    """DELETE semantic -> audit delete/semantic, target_id == id borrado, hash = sha256(id)."""
    user = await _seed_user(db_session)
    semantic, procedural, audit = _make_stores(db_session, user.id)

    created = await semantic.add(SemanticMemoryCreate(content="hecho a borrar"))
    target_id = str(created.id)

    ops = [MemoryOp(op="DELETE", layer="semantic", target_id=target_id)]
    applied = await apply_ops(
        ops,
        semantic_store=semantic,
        procedural_store=procedural,
        audit_store=audit,
        origin_model=LlmModel.QWEN,
        origin_mode=Mode.VIDA,
    )
    assert applied == 1

    rows = await _fetch_audit_rows(db_session, user.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.operation == AuditOperation.DELETE
    assert row.target_layer == MemoryLayer.SEMANTIC
    assert row.target_id == created.id
    assert row.record_hash == _sha256(target_id)


# ---------------------------------------------------------------------------
# 4. ADD procedural -> write ; UPDATE procedural -> update
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_apply_ops_add_procedural_writes_audit(db_session: AsyncSession) -> None:
    """ADD procedural -> audit write/procedural, target_id == id de la entrada, hash estable."""
    user = await _seed_user(db_session)
    semantic, procedural, audit = _make_stores(db_session, user.id)

    key = "idioma_preferido"
    value = {"idioma": "es-AR", "tono": "informal"}
    ops = [MemoryOp(op="ADD", layer="procedural", key=key, value=value)]
    applied = await apply_ops(
        ops,
        semantic_store=semantic,
        procedural_store=procedural,
        audit_store=audit,
        origin_model=LlmModel.QWEN,
        origin_mode=Mode.VIDA,
    )
    assert applied == 1

    entry = await procedural.get(key)
    assert entry is not None

    rows = await _fetch_audit_rows(db_session, user.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.operation == AuditOperation.WRITE
    assert row.target_layer == MemoryLayer.PROCEDURAL
    assert row.target_id == entry.id
    expected_hash = _sha256(key + chr(10) + json.dumps(value, sort_keys=True, ensure_ascii=False))
    assert row.record_hash == expected_hash


@pytest.mark.integration
async def test_apply_ops_update_procedural_writes_audit(db_session: AsyncSession) -> None:
    """UPDATE procedural (vía upsert) -> audit con operation=update, target_id de la entrada."""
    user = await _seed_user(db_session)
    semantic, procedural, audit = _make_stores(db_session, user.id)

    # Sembramos la entrada directo (sin auditar) para que el UPDATE refuerce la existente.
    await procedural.upsert(ProceduralMemoryUpsert(key="tono", value={"tono": "formal"}))

    new_value = {"tono": "informal"}
    ops = [MemoryOp(op="UPDATE", layer="procedural", key="tono", value=new_value)]
    applied = await apply_ops(
        ops,
        semantic_store=semantic,
        procedural_store=procedural,
        audit_store=audit,
        origin_model=LlmModel.QWEN,
        origin_mode=Mode.VIDA,
    )
    assert applied == 1

    entry = await procedural.get("tono")
    assert entry is not None

    rows = await _fetch_audit_rows(db_session, user.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.operation == AuditOperation.UPDATE
    assert row.target_layer == MemoryLayer.PROCEDURAL
    assert row.target_id == entry.id
    expected_hash = _sha256(
        "tono" + chr(10) + json.dumps(new_value, sort_keys=True, ensure_ascii=False)
    )
    assert row.record_hash == expected_hash


# ---------------------------------------------------------------------------
# 5. DELETE procedural -> delete con target_id NULL
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_apply_ops_delete_procedural_writes_audit_null_target(
    db_session: AsyncSession,
) -> None:
    """DELETE procedural -> audit delete/procedural con target_id NULL, hash = sha256(key)."""
    user = await _seed_user(db_session)
    semantic, procedural, audit = _make_stores(db_session, user.id)

    await procedural.upsert(ProceduralMemoryUpsert(key="pref_a_borrar", value={"x": 1}))

    ops = [MemoryOp(op="DELETE", layer="procedural", key="pref_a_borrar")]
    applied = await apply_ops(
        ops,
        semantic_store=semantic,
        procedural_store=procedural,
        audit_store=audit,
        origin_model=LlmModel.QWEN,
        origin_mode=Mode.VIDA,
    )
    assert applied == 1

    rows = await _fetch_audit_rows(db_session, user.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.operation == AuditOperation.DELETE
    assert row.target_layer == MemoryLayer.PROCEDURAL
    assert row.target_id is None
    assert row.record_hash == _sha256("pref_a_borrar")


# ---------------------------------------------------------------------------
# 6. NOOP y ops skippeadas -> NINGUNA fila de audit
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_apply_ops_noop_and_skipped_write_no_audit(db_session: AsyncSession) -> None:
    """NOOP + ops skippeadas (sin content/key/target_id) -> 0 ops aplicadas, 0 filas audit."""
    user = await _seed_user(db_session)
    semantic, procedural, audit = _make_stores(db_session, user.id)

    ops = [
        MemoryOp(op="NOOP", layer="semantic"),
        MemoryOp(op="ADD", layer="semantic", content=""),  # sin content -> skip
        MemoryOp(op="ADD", layer="procedural", key=None, value={"x": 1}),  # sin key -> skip
        MemoryOp(op="DELETE", layer="semantic", target_id=None),  # sin target_id -> skip
        MemoryOp(op="DELETE", layer="procedural", key=None),  # sin key -> skip
        # UPDATE semantic a un target_id inexistente -> no matchea -> no audita.
        MemoryOp(op="UPDATE", layer="semantic", content="x", target_id=str(uuid.uuid4())),
        # DELETE procedural de una key inexistente -> no matchea -> no audita.
        MemoryOp(op="DELETE", layer="procedural", key="no_existe"),
    ]
    applied = await apply_ops(
        ops,
        semantic_store=semantic,
        procedural_store=procedural,
        audit_store=audit,
        origin_model=LlmModel.QWEN,
        origin_mode=Mode.VIDA,
    )
    assert applied == 0

    rows = await _fetch_audit_rows(db_session, user.id)
    assert rows == [], "ni NOOP ni ops skippeadas/no-matcheadas deben escribir audit"


# ---------------------------------------------------------------------------
# 7. REGLA #4 — la fila de audit NO contiene el plaintext
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_audit_row_never_contains_plaintext(db_session: AsyncSession) -> None:
    """La fila de audit NO guarda el contenido en claro; el record_hash es sha256 (64 hex)."""
    user = await _seed_user(db_session)
    semantic, procedural, audit = _make_stores(db_session, user.id)

    plaintext = "El usuario tiene un secreto muy específico que no debe filtrarse."
    ops = [MemoryOp(op="ADD", layer="semantic", content=plaintext)]
    await apply_ops(
        ops,
        semantic_store=semantic,
        procedural_store=procedural,
        audit_store=audit,
        origin_model=LlmModel.QWEN,
        origin_mode=Mode.VIDA,
    )

    rows = await _fetch_audit_rows(db_session, user.id)
    assert len(rows) == 1
    row = rows[0]

    # El plaintext NO aparece en NINGUNA columna textual de la fila.
    serialized = " ".join(
        str(v)
        for v in (
            row.operation,
            row.target_layer,
            row.target_id,
            row.origin_model,
            row.origin_mode,
            row.origin_tool,
            row.record_hash,
            row.sensitive,
        )
    )
    assert plaintext not in serialized
    assert "secreto" not in serialized

    # El record_hash es exactamente el sha256 hex de 64 chars del contenido.
    assert len(row.record_hash) == 64
    assert all(c in "0123456789abcdef" for c in row.record_hash)
    assert row.record_hash == _sha256(plaintext)


# ---------------------------------------------------------------------------
# 8. apply_ops sin audit_store -> ningún cambio de comportamiento (back-compat)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_apply_ops_without_audit_store_writes_no_audit(db_session: AsyncSession) -> None:
    """Sin ``audit_store`` (default None), apply_ops aplica las ops pero NO audita."""
    user = await _seed_user(db_session)
    semantic, procedural, _audit = _make_stores(db_session, user.id)

    ops = [MemoryOp(op="ADD", layer="semantic", content="hecho sin auditoría")]
    applied = await apply_ops(ops, semantic_store=semantic, procedural_store=procedural)
    assert applied == 1

    rows = await _fetch_audit_rows(db_session, user.id)
    assert rows == [], "sin audit_store no debe escribirse ninguna fila de audit"


# ---------------------------------------------------------------------------
# 9. Consolidación end-to-end -> N ops escriben N filas de audit
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_consolidate_end_to_end_writes_n_audit_rows(db_session: AsyncSession) -> None:
    """``_async_consolidate`` con N ops aplicadas escribe N filas de audit (write).

    Usa el camino real (``QwenMemoryEngine`` sobre un ``FakeLlmClient`` con ops
    encoladas) + la session inyectada del fixture, que es como corre el branch de
    test de ``_async_consolidate``: construye el ``AuditStore`` y lo pasa a
    ``apply_ops``.
    """
    user = await _seed_user(db_session)
    user_id = str(user.id)
    # Sesión real: el ADD semantic persiste source_session_id (FK a sessions.id).
    session_id = await _seed_session(db_session, user.id)

    ops_json = json.dumps(
        [
            {"op": "ADD", "layer": "semantic", "content": "El usuario es vegetariano."},
            {"op": "ADD", "layer": "procedural", "key": "idioma", "value": {"lang": "es-AR"}},
            {"op": "NOOP", "layer": "semantic"},
        ]
    )
    client = _make_llm_with_ops(ops_json)

    applied = await _async_consolidate(
        user_id=user_id,
        session_id=str(session_id),
        user_msg="no como carne y hablo castellano",
        model_response="anotado",
        mode="vida",
        llm_client=client,
        embedder=FakeEmbeddingClient(),
        reranker=FakeReranker(),
        session=db_session,
    )
    # 2 ops aplicadas (semantic ADD + procedural ADD); el NOOP no cuenta.
    assert applied == 2

    rows = await _fetch_audit_rows(db_session, user.id)
    # Exactamente 2 filas de audit: una por op aplicada (el NOOP no audita).
    assert len(rows) == 2
    layers = {row.target_layer for row in rows}
    assert layers == {MemoryLayer.SEMANTIC, MemoryLayer.PROCEDURAL}
    assert all(row.operation == AuditOperation.WRITE for row in rows)
    assert all(row.origin_model == LlmModel.QWEN for row in rows)
    assert all(row.origin_mode == Mode.VIDA for row in rows)


@pytest.mark.integration
async def test_consolidate_with_fake_engine_writes_audit(db_session: AsyncSession) -> None:
    """Sanity con ``FakeMemoryEngine``: 3 ops aplicadas -> 3 filas de audit vía apply_ops.

    Ejercita ``apply_ops`` + ``AuditStore`` con ops construidas a mano (sin pasar
    por el parseo de Qwen), cubriendo las 3 capas/operaciones en un solo turno.
    """
    user = await _seed_user(db_session)
    semantic, procedural, audit = _make_stores(db_session, user.id)

    # FakeMemoryEngine para reflejar el patrón de extracción (sin LLM real).
    engine = FakeMemoryEngine(
        ops=[
            MemoryOp(op="ADD", layer="semantic", content="El usuario nació en Córdoba."),
            MemoryOp(op="ADD", layer="procedural", key="ciudad", value={"ciudad": "Córdoba"}),
            MemoryOp(op="NOOP", layer="semantic"),
        ]
    )
    ops = await engine.consolidate(
        user_msg="nací en Córdoba", model_response="qué lindo", mode="vida"
    )

    applied = await apply_ops(
        ops,
        semantic_store=semantic,
        procedural_store=procedural,
        audit_store=audit,
        origin_model=LlmModel.QWEN,
        origin_mode=Mode.VIDA,
    )
    assert applied == 2

    rows = await _fetch_audit_rows(db_session, user.id)
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Aislamiento transaccional: un fallo de audit NO envenena la transacción
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_audit_failure_is_isolated_by_savepoint(db_session: AsyncSession) -> None:
    """Un fallo de escritura de audit NO envenena la transacción (savepoint por-op).

    Con ``session`` pasada, cada op + su audit corren en un ``begin_nested``. Si el
    audit falla a nivel DB, en Postgres ese statement abortaría TODA la transacción;
    el savepoint acota el rollback a esa sola op. Sin él, las ops siguientes
    fallarían con PendingRollbackError y el commit final tumbaría el worker.

    Se inyecta un AuditStore que fuerza un fallo a nivel DB (record_hash inválido,
    bypasseando la validación del store) y se verifica que: (a) la op se revierte
    (applied=0, nada persiste) y (b) la sesión sigue USABLE tras el fallo.
    """
    user = await _seed_user(db_session)
    semantic, procedural, _ = _make_stores(db_session, user.id)

    class _BadAuditStore(AuditStore):
        async def record(self, **_kwargs: object) -> None:
            # Bypassea la validación del store: inserta un record_hash que viola el
            # CHECK del modelo -> abort a nivel DB en el flush (escenario que el
            # savepoint debe contener).
            self._session.add(
                AuditLog(
                    user_id=self._user_id,
                    operation=AuditOperation.WRITE,
                    target_layer=MemoryLayer.SEMANTIC,
                    target_id=None,
                    record_hash="no-es-un-sha256",
                )
            )
            await self._session.flush()

    bad_audit = _BadAuditStore(db_session, user.id)
    ops = [MemoryOp(op="ADD", layer="semantic", content="hecho que no debería persistir")]

    # NO propaga: el except por-op atrapa el fallo del savepoint.
    applied = await apply_ops(
        ops,
        session=db_session,
        semantic_store=semantic,
        procedural_store=procedural,
        audit_store=bad_audit,
        origin_model=LlmModel.QWEN,
        origin_mode=Mode.VIDA,
    )
    # El audit falló -> el savepoint revirtió la op -> no contó ni persistió.
    assert applied == 0

    # CLAVE: la sesión NO quedó envenenada -> queries post-fallo funcionan (sin
    # PendingRollbackError), y ni la fila de audit ni el hecho persistieron.
    audit_count = (
        await db_session.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.user_id == user.id)
        )
    ).scalar_one()
    assert audit_count == 0
    fact_count = (
        await db_session.execute(
            select(func.count())
            .select_from(SemanticMemory)
            .where(SemanticMemory.user_id == user.id)
        )
    ).scalar_one()
    assert fact_count == 0
