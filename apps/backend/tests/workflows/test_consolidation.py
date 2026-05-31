"""Tests de la task de consolidacion de memoria (M8 Ola 2).

UNIT: validan el wrapper ``consolidate_turn`` sin DB ni red.
INTEGRATION: validan ``_async_consolidate`` contra la DB de tests real
  (``@pytest.mark.integration``).

Reglas aplicadas:
- Ningun dato de usuario en logs (regla #4): el contenido de turno va en
  variables; no se imprimen.
- ``session_id`` es OPACO: no se usa como FK ni se pasa como
  ``source_session_id``.
- El wrapper ``consolidate_turn`` nunca propaga excepciones.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import Mode
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.reranker import FakeReranker
from app.llm.schemas import CompletionResult
from app.memory.procedural import ProceduralMemoryStore
from app.memory.semantic import SemanticMemoryStore
from app.models.memory import SemanticMemory
from app.models.session import ChatSession
from app.models.user import User
from app.workflows.consolidation import _async_consolidate, consolidate_turn

# ---------------------------------------------------------------------------
# Helper de siembra de usuario (solo para tests de integracion)
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession) -> str:
    """Inserta un User minimo y devuelve su UUID como string.

    Flush sin commit: el rollback del fixture limpia al final.
    La FK de semantic_memory/procedural_memory requiere un user real en la DB.
    """
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return str(user.id)


async def _seed_session(session: AsyncSession, user_id: str, mode: Mode = Mode.VIDA) -> str:
    """Inserta una ``ChatSession`` real para ``user_id`` y devuelve su UUID como str.

    La FK ``semantic_memory.source_session_id`` -> ``sessions.id`` requiere una
    fila real en ``sessions`` para que el INSERT no viole la FK (M10 Ola 1).
    Flush sin commit: el rollback del fixture limpia al final.
    """
    chat_session = ChatSession(user_id=UUID(user_id), mode=mode)
    session.add(chat_session)
    await session.flush()
    await session.refresh(chat_session)
    return str(chat_session.id)


async def _fetch_only_semantic_row(session: AsyncSession, user_id: str) -> SemanticMemory:
    """Trae la unica fila de ``semantic_memory`` del usuario (lectura directa).

    Lee el modelo crudo (no via ``store.search``, que descifra + rerankea) para
    inspeccionar ``source_session_id`` tal cual quedo en la DB, incluido el caso
    NULL tras el ``ondelete=SET NULL``.
    """
    stmt = select(SemanticMemory).where(SemanticMemory.user_id == UUID(user_id))
    rows = list((await session.execute(stmt)).scalars().all())
    assert len(rows) == 1, f"se esperaba 1 fila semantic, hay {len(rows)}"
    return rows[0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

USER_ID = str(uuid.uuid4())
SESSION_ID = str(uuid.uuid4())
MODE = "vida"


def _make_llm_with_ops(ops_json: str) -> FakeLlmClient:
    """FakeLlmClient con un resultado ya encolado cuyo text es ops_json."""
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
# UNIT tests — sin DB ni red
# ---------------------------------------------------------------------------


class TestConsolidateTurnWrapper:
    """Tests del wrapper Celery ``consolidate_turn``."""

    def test_calls_async_consolidate_with_correct_args(self) -> None:
        """El wrapper llama a ``_async_consolidate`` con los args correctos."""
        with patch(
            "app.workflows.consolidation._async_consolidate", new_callable=AsyncMock
        ) as mock_async:
            mock_async.return_value = 2

            consolidate_turn(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="hola",
                model_response="chau",
                mode=MODE,
            )

            mock_async.assert_called_once_with(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="hola",
                model_response="chau",
                mode=MODE,
            )

    def test_does_not_propagate_if_async_consolidate_raises(self) -> None:
        """Si ``_async_consolidate`` lanza, el wrapper NO propaga (regla worker)."""
        with patch(
            "app.workflows.consolidation._async_consolidate", new_callable=AsyncMock
        ) as mock_async:
            mock_async.side_effect = RuntimeError("DB caida")

            # No debe lanzar
            consolidate_turn(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="algo",
                model_response="respuesta",
                mode=MODE,
            )

    def test_does_not_propagate_if_asyncio_run_raises(self) -> None:
        """Cualquier excepcion dentro del try queda silenciada."""
        with patch("app.workflows.consolidation.asyncio.run") as mock_run:
            mock_run.side_effect = ValueError("loop error")

            # No debe lanzar
            consolidate_turn(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="x",
                model_response="y",
                mode=MODE,
            )

    def test_task_name_is_correct(self) -> None:
        """La task esta registrada con el nombre correcto."""
        assert consolidate_turn.name == "workflows.consolidate_turn"

    def test_returns_none_on_success(self) -> None:
        """El wrapper devuelve None (la task Celery no necesita resultado)."""
        with patch(
            "app.workflows.consolidation._async_consolidate", new_callable=AsyncMock
        ) as mock_async:
            mock_async.return_value = 1
            result = consolidate_turn(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="msg",
                model_response="resp",
                mode=MODE,
            )
        assert result is None


class TestAsyncConsolidateUnit:
    """Tests unit de ``_async_consolidate`` con session inyectada (sin DB real)."""

    async def test_returns_zero_when_llm_returns_noop(self) -> None:
        """Si Qwen devuelve solo NOOP, ``_async_consolidate`` retorna 0."""
        ops_json = json.dumps([{"op": "NOOP", "layer": "semantic"}])
        client = _make_llm_with_ops(ops_json)
        session = MagicMock(spec=AsyncSession)

        # Mockear stores para evitar llamadas a DB
        with (
            patch("app.workflows.consolidation.SemanticMemoryStore") as mock_sem,
            patch("app.workflows.consolidation.ProceduralMemoryStore") as mock_proc,
        ):
            mock_sem.return_value = AsyncMock()
            mock_proc.return_value = AsyncMock()

            result = await _async_consolidate(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="sin info relevante",
                model_response="ok",
                mode=MODE,
                llm_client=client,
                embedder=FakeEmbeddingClient(),
                reranker=FakeReranker(),
                session=session,
            )

        assert result == 0

    async def test_returns_applied_count_for_add_ops(self) -> None:
        """Con un ADD semantic valido, el resultado es 1 (una op aplicada)."""
        ops_json = json.dumps(
            [{"op": "ADD", "layer": "semantic", "content": "El usuario es vegetariano."}]
        )
        client = _make_llm_with_ops(ops_json)

        # Usar mocks para que add() no llame a la DB
        mock_sem = AsyncMock()
        mock_sem.add = AsyncMock(return_value=MagicMock())
        mock_proc = AsyncMock()

        session = MagicMock(spec=AsyncSession)

        with (
            patch("app.workflows.consolidation.SemanticMemoryStore", return_value=mock_sem),
            patch("app.workflows.consolidation.ProceduralMemoryStore", return_value=mock_proc),
        ):
            result = await _async_consolidate(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="no como carne",
                model_response="anotado",
                mode=MODE,
                llm_client=client,
                embedder=FakeEmbeddingClient(),
                reranker=FakeReranker(),
                session=session,
            )

        assert result == 1
        mock_sem.add.assert_called_once()

    async def test_passes_source_session_id_to_add_op(self) -> None:
        """La op ADD semantic incluye source_session_id == UUID(session_id) (M10 Ola 1)."""
        ops_json = json.dumps(
            [{"op": "ADD", "layer": "semantic", "content": "El usuario vive en Buenos Aires."}]
        )
        client = _make_llm_with_ops(ops_json)

        captured_payloads: list = []

        async def capture_add(payload):
            captured_payloads.append(payload)
            return MagicMock(id=uuid.uuid4())

        mock_sem = AsyncMock()
        mock_sem.add = capture_add
        session = MagicMock(spec=AsyncSession)

        with (
            patch("app.workflows.consolidation.SemanticMemoryStore", return_value=mock_sem),
            patch("app.workflows.consolidation.ProceduralMemoryStore", return_value=AsyncMock()),
        ):
            await _async_consolidate(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="vivo en BA",
                model_response="ok",
                mode=MODE,
                llm_client=client,
                embedder=FakeEmbeddingClient(),
                reranker=FakeReranker(),
                session=session,
            )

        assert len(captured_payloads) == 1
        # source_session_id == el UUID del session_id real (provenance, M10 Ola 1).
        assert captured_payloads[0].source_session_id == UUID(SESSION_ID)

    async def test_garbage_session_id_passes_none_without_crash(self) -> None:
        """Un session_id no-UUID degrada a None sin crashear (parse defensivo)."""
        ops_json = json.dumps(
            [{"op": "ADD", "layer": "semantic", "content": "El usuario juega al tenis."}]
        )
        client = _make_llm_with_ops(ops_json)

        captured_payloads: list = []

        async def capture_add(payload):
            captured_payloads.append(payload)
            return MagicMock(id=uuid.uuid4())

        mock_sem = AsyncMock()
        mock_sem.add = capture_add
        session = MagicMock(spec=AsyncSession)

        with (
            patch("app.workflows.consolidation.SemanticMemoryStore", return_value=mock_sem),
            patch("app.workflows.consolidation.ProceduralMemoryStore", return_value=AsyncMock()),
        ):
            result = await _async_consolidate(
                user_id=USER_ID,
                session_id="no-soy-un-uuid",
                user_msg="juego tenis",
                model_response="ok",
                mode=MODE,
                llm_client=client,
                embedder=FakeEmbeddingClient(),
                reranker=FakeReranker(),
                session=session,
            )

        # La op igual se aplica; el parse fallido NO tumba la consolidacion.
        assert result == 1
        assert len(captured_payloads) == 1
        assert captured_payloads[0].source_session_id is None

    async def test_invalid_json_from_llm_returns_zero(self) -> None:
        """JSON invalido de Qwen -> parseo defensivo -> 0 ops aplicadas, sin crash."""
        client = FakeLlmClient(served_models=frozenset({"qwen"}))
        client.queue_result(
            CompletionResult(
                text="esto no es JSON { invalido",
                finish_reason="stop",
                prompt_tokens=5,
                completion_tokens=10,
                model_name="qwen",
                latency_ms=2.0,
            )
        )
        session = MagicMock(spec=AsyncSession)

        with (
            patch("app.workflows.consolidation.SemanticMemoryStore", return_value=AsyncMock()),
            patch("app.workflows.consolidation.ProceduralMemoryStore", return_value=AsyncMock()),
        ):
            result = await _async_consolidate(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="hola",
                model_response="chau",
                mode=MODE,
                llm_client=client,
                embedder=FakeEmbeddingClient(),
                reranker=FakeReranker(),
                session=session,
            )

        assert result == 0

    async def test_procedural_add_op_applied(self) -> None:
        """Un ADD procedural valido se aplica via ``procedural_store.upsert``."""
        ops_json = json.dumps(
            [
                {
                    "op": "ADD",
                    "layer": "procedural",
                    "key": "dieta",
                    "value": {"tipo": "vegetariana"},
                }
            ]
        )
        client = _make_llm_with_ops(ops_json)

        mock_proc = AsyncMock()
        mock_proc.upsert = AsyncMock(return_value=MagicMock())
        session = MagicMock(spec=AsyncSession)

        with (
            patch("app.workflows.consolidation.SemanticMemoryStore", return_value=AsyncMock()),
            patch("app.workflows.consolidation.ProceduralMemoryStore", return_value=mock_proc),
        ):
            result = await _async_consolidate(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="soy vegano",
                model_response="ok",
                mode=MODE,
                llm_client=client,
                embedder=FakeEmbeddingClient(),
                reranker=FakeReranker(),
                session=session,
            )

        assert result == 1
        mock_proc.upsert.assert_called_once()

    async def test_mixed_ops_count(self) -> None:
        """ADD semantic + ADD procedural = 2 ops aplicadas."""
        ops_json = json.dumps(
            [
                {"op": "ADD", "layer": "semantic", "content": "El usuario tiene 30 anos."},
                {
                    "op": "ADD",
                    "layer": "procedural",
                    "key": "idioma",
                    "value": {"lang": "es-AR"},
                },
            ]
        )
        client = _make_llm_with_ops(ops_json)

        mock_sem = AsyncMock()
        mock_sem.add = AsyncMock(return_value=MagicMock())
        mock_proc = AsyncMock()
        mock_proc.upsert = AsyncMock(return_value=MagicMock())
        session = MagicMock(spec=AsyncSession)

        with (
            patch("app.workflows.consolidation.SemanticMemoryStore", return_value=mock_sem),
            patch("app.workflows.consolidation.ProceduralMemoryStore", return_value=mock_proc),
        ):
            result = await _async_consolidate(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="tengo 30 y hablo castellano",
                model_response="ok",
                mode=MODE,
                llm_client=client,
                embedder=FakeEmbeddingClient(),
                reranker=FakeReranker(),
                session=session,
            )

        assert result == 2

    async def test_store_exception_does_not_propagate(self) -> None:
        """Si un store lanza en ``apply_ops``, la task no propaga (robustez)."""
        ops_json = json.dumps([{"op": "ADD", "layer": "semantic", "content": "dato cualquiera"}])
        client = _make_llm_with_ops(ops_json)

        mock_sem = AsyncMock()
        mock_sem.add = AsyncMock(side_effect=RuntimeError("DB error"))
        session = MagicMock(spec=AsyncSession)

        with (
            patch("app.workflows.consolidation.SemanticMemoryStore", return_value=mock_sem),
            patch("app.workflows.consolidation.ProceduralMemoryStore", return_value=AsyncMock()),
        ):
            # apply_ops absorbe el error individual -> no propaga
            result = await _async_consolidate(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="algo",
                model_response="resp",
                mode=MODE,
                llm_client=client,
                embedder=FakeEmbeddingClient(),
                reranker=FakeReranker(),
                session=session,
            )

        assert result == 0


# ---------------------------------------------------------------------------
# INTEGRATION tests — contra DB de tests real
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAsyncConsolidateIntegration:
    """Tests de integracion de ``_async_consolidate`` contra la DB de tests.

    Usa ``db_session`` (function-scoped, rollback al final) para no persistir
    datos entre tests. Los stores usan la misma sesion que el fixture.
    """

    async def test_semantic_add_persisted_and_searchable(self, db_session: AsyncSession) -> None:
        """Un ADD semantic se persiste y se puede buscar con ``search``."""
        user_id = await _seed_user(db_session)
        session_id = await _seed_session(db_session, user_id)
        ops_json = json.dumps(
            [{"op": "ADD", "layer": "semantic", "content": "El usuario es vegetariano."}]
        )
        client = _make_llm_with_ops(ops_json)
        embedder = FakeEmbeddingClient()
        reranker = FakeReranker()

        applied = await _async_consolidate(
            user_id=user_id,
            session_id=session_id,
            user_msg="no como carne",
            model_response="anotado que sos vegetariano",
            mode=MODE,
            llm_client=client,
            embedder=embedder,
            reranker=reranker,
            session=db_session,
        )

        assert applied == 1

        # Verificar que el hecho quedo en la DB buscandolo
        store = SemanticMemoryStore(db_session, UUID(user_id), embedder, reranker)
        results = await store.search("vegetariano", limit=5)
        assert len(results) >= 1
        contents = [r.content for r in results]
        assert any("vegetariano" in c for c in contents)

    async def test_procedural_add_persisted_and_retrievable(self, db_session: AsyncSession) -> None:
        """Un ADD procedural se persiste y se puede recuperar con ``get``."""
        user_id = await _seed_user(db_session)
        ops_json = json.dumps(
            [
                {
                    "op": "ADD",
                    "layer": "procedural",
                    "key": "dieta_preferida",
                    "value": {"tipo": "vegana", "restricciones": ["lacteos", "huevos"]},
                }
            ]
        )
        client = _make_llm_with_ops(ops_json)

        applied = await _async_consolidate(
            user_id=user_id,
            session_id=SESSION_ID,
            user_msg="soy vegano",
            model_response="ok, anotado",
            mode=MODE,
            llm_client=client,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            session=db_session,
        )

        assert applied == 1

        # Verificar recuperacion por clave
        proc_store = ProceduralMemoryStore(db_session, UUID(user_id))
        entry = await proc_store.get("dieta_preferida")
        assert entry is not None
        assert entry.value["tipo"] == "vegana"
        assert "lacteos" in entry.value["restricciones"]

    async def test_semantic_and_procedural_both_applied(self, db_session: AsyncSession) -> None:
        """ADD semantic + ADD procedural en el mismo turno: ambos se persisten."""
        user_id = await _seed_user(db_session)
        session_id = await _seed_session(db_session, user_id)
        ops_json = json.dumps(
            [
                {"op": "ADD", "layer": "semantic", "content": "El usuario trabaja como disenador."},
                {
                    "op": "ADD",
                    "layer": "procedural",
                    "key": "ocupacion",
                    "value": {"rol": "disenador", "area": "UX"},
                },
            ]
        )
        client = _make_llm_with_ops(ops_json)
        embedder = FakeEmbeddingClient()
        reranker = FakeReranker()

        applied = await _async_consolidate(
            user_id=user_id,
            session_id=session_id,
            user_msg="trabajo como disenador UX",
            model_response="ok",
            mode=MODE,
            llm_client=client,
            embedder=embedder,
            reranker=reranker,
            session=db_session,
        )

        assert applied == 2

        # Verificar semantic
        sem_store = SemanticMemoryStore(db_session, UUID(user_id), embedder, reranker)
        results = await sem_store.search("disenador", limit=5)
        assert any("disenador" in r.content for r in results)

        # Verificar procedural
        proc_store = ProceduralMemoryStore(db_session, UUID(user_id))
        entry = await proc_store.get("ocupacion")
        assert entry is not None
        assert entry.value["rol"] == "disenador"

    async def test_noop_applies_zero_ops(self, db_session: AsyncSession) -> None:
        """NOOP no escribe nada en la DB."""
        user_id = await _seed_user(db_session)
        ops_json = json.dumps([{"op": "NOOP", "layer": "semantic"}])
        client = _make_llm_with_ops(ops_json)

        applied = await _async_consolidate(
            user_id=user_id,
            session_id=SESSION_ID,
            user_msg="que hora es",
            model_response="son las 3pm",
            mode=MODE,
            llm_client=client,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            session=db_session,
        )

        assert applied == 0

    async def test_source_session_id_set_to_chat_session_id(self, db_session: AsyncSession) -> None:
        """El ADD semantic persiste source_session_id == ChatSession.id (M10 Ola 1, FK)."""
        user_id = await _seed_user(db_session)
        session_id = await _seed_session(db_session, user_id)
        ops_json = json.dumps(
            [
                {
                    "op": "ADD",
                    "layer": "semantic",
                    "content": "El usuario tiene un perro llamado Luna.",
                }
            ]
        )
        client = _make_llm_with_ops(ops_json)
        embedder = FakeEmbeddingClient()
        reranker = FakeReranker()

        applied = await _async_consolidate(
            user_id=user_id,
            session_id=session_id,
            user_msg="mi perro se llama Luna",
            model_response="que nombre lindo",
            mode=MODE,
            llm_client=client,
            embedder=embedder,
            reranker=reranker,
            session=db_session,
        )

        assert applied == 1
        # La provenance quedo seteada a la FK real (sessions.id).
        row = await _fetch_only_semantic_row(db_session, user_id)
        assert row.source_session_id == UUID(session_id)

        # Y se expone tambien en el Out de search (mismo valor).
        store = SemanticMemoryStore(db_session, UUID(user_id), embedder, reranker)
        results = await store.search("perro", limit=5)
        assert len(results) >= 1
        assert all(r.source_session_id == UUID(session_id) for r in results)

    async def test_source_session_id_nulled_on_session_delete(
        self, db_session: AsyncSession
    ) -> None:
        """Borrar la ChatSession deja source_session_id NULL (ondelete=SET NULL)."""
        user_id = await _seed_user(db_session)
        session_id = await _seed_session(db_session, user_id)
        ops_json = json.dumps(
            [{"op": "ADD", "layer": "semantic", "content": "El usuario nacio en Cordoba."}]
        )
        client = _make_llm_with_ops(ops_json)
        embedder = FakeEmbeddingClient()
        reranker = FakeReranker()

        applied = await _async_consolidate(
            user_id=user_id,
            session_id=session_id,
            user_msg="naci en Cordoba",
            model_response="que lindo",
            mode=MODE,
            llm_client=client,
            embedder=embedder,
            reranker=reranker,
            session=db_session,
        )
        assert applied == 1

        # Precondicion: la provenance apunta a la sesion.
        row = await _fetch_only_semantic_row(db_session, user_id)
        assert row.source_session_id == UUID(session_id)

        # Borrar la ChatSession: el FK ondelete=SET NULL debe anular la provenance
        # SIN borrar el hecho (la memoria sobrevive a la sesion que la origino).
        await db_session.execute(sa_delete(ChatSession).where(ChatSession.id == UUID(session_id)))
        await db_session.flush()
        # Invalidar el estado cacheado del ORM para releer la fila desde la DB.
        db_session.expire_all()

        row_after = await _fetch_only_semantic_row(db_session, user_id)
        assert row_after.source_session_id is None
        # El hecho sigue existiendo (no se borro en cascada).
        assert row_after.id == row.id

    async def test_garbage_session_id_persists_with_null_provenance(
        self, db_session: AsyncSession
    ) -> None:
        """Un session_id no-UUID persiste el hecho con source_session_id NULL, sin crash."""
        user_id = await _seed_user(db_session)
        ops_json = json.dumps(
            [{"op": "ADD", "layer": "semantic", "content": "El usuario toca la guitarra."}]
        )
        client = _make_llm_with_ops(ops_json)
        embedder = FakeEmbeddingClient()
        reranker = FakeReranker()

        # session_id basura: el parse defensivo degrada a None y NO crashea.
        applied = await _async_consolidate(
            user_id=user_id,
            session_id="esto-no-es-un-uuid-valido",
            user_msg="toco la guitarra",
            model_response="genial",
            mode=MODE,
            llm_client=client,
            embedder=embedder,
            reranker=reranker,
            session=db_session,
        )

        assert applied == 1
        row = await _fetch_only_semantic_row(db_session, user_id)
        assert row.source_session_id is None

    async def test_invalid_json_no_db_writes(self, db_session: AsyncSession) -> None:
        """JSON invalido del LLM no escribe nada en la DB (parseo defensivo)."""
        user_id = await _seed_user(db_session)
        client = FakeLlmClient(served_models=frozenset({"qwen"}))
        client.queue_result(
            CompletionResult(
                text="no soy json :((",
                finish_reason="stop",
                prompt_tokens=5,
                completion_tokens=5,
                model_name="qwen",
                latency_ms=1.0,
            )
        )
        embedder = FakeEmbeddingClient()
        reranker = FakeReranker()

        applied = await _async_consolidate(
            user_id=user_id,
            session_id=SESSION_ID,
            user_msg="algo",
            model_response="resp",
            mode=MODE,
            llm_client=client,
            embedder=embedder,
            reranker=reranker,
            session=db_session,
        )

        assert applied == 0

        # Nada en DB para ese user_id
        proc_store = ProceduralMemoryStore(db_session, UUID(user_id))
        all_proc = await proc_store.list_all()
        assert all_proc == []

    async def test_user_isolation(self, db_session: AsyncSession) -> None:
        """Cada user_id solo ve sus propios datos (aislamiento por construccion)."""
        user_a = await _seed_user(db_session)
        user_b = await _seed_user(db_session)
        session_a = await _seed_session(db_session, user_a)
        embedder = FakeEmbeddingClient()
        reranker = FakeReranker()

        # user_a: ADD semantic
        ops_a = json.dumps(
            [{"op": "ADD", "layer": "semantic", "content": "El usuario A tiene 25 anos."}]
        )
        client_a = _make_llm_with_ops(ops_a)
        await _async_consolidate(
            user_id=user_a,
            session_id=session_a,
            user_msg="tengo 25",
            model_response="ok",
            mode=MODE,
            llm_client=client_a,
            embedder=embedder,
            reranker=reranker,
            session=db_session,
        )

        # user_b: no escribe nada
        client_b = _make_llm_with_ops(json.dumps([{"op": "NOOP", "layer": "semantic"}]))
        await _async_consolidate(
            user_id=user_b,
            session_id=SESSION_ID,
            user_msg="hola",
            model_response="hola",
            mode=MODE,
            llm_client=client_b,
            embedder=embedder,
            reranker=reranker,
            session=db_session,
        )

        # user_b NO ve los datos de user_a
        store_b = SemanticMemoryStore(db_session, UUID(user_b), embedder, reranker)
        results_b = await store_b.search("25 anos", limit=5)
        assert results_b == []

        # user_a SI ve su propio dato
        store_a = SemanticMemoryStore(db_session, UUID(user_a), embedder, reranker)
        results_a = await store_a.search("25 anos", limit=5)
        assert len(results_a) >= 1
