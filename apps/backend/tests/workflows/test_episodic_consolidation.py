"""Tests de la consolidacion episodica (issue #209).

UNIT: el wrapper ``consolidate_session`` (firma JSON, fail-open, no propaga) y
  ``_async_consolidate_session`` con session inyectada (0 turnos -> 0, transcript
  -> 1 episodio, JSON corrupto de Qwen -> parseo defensivo, is_sensitive bienestar
  con retention <= 365).
INTEGRATION (``@pytest.mark.integration``, DB real): close -> exactamente 1
  episodio cifrado con embedding + turnos purgados; idempotencia doble-cierre -> 1
  episodio; audit_log 1 fila WRITE/EPISODIC; no-leak de PII en logs; robustez del
  worker (payload corrupto no tumba).

Reglas aplicadas:
- Ningun dato de usuario en logs (regla #4): el contenido va en variables.
- El wrapper ``consolidate_session`` nunca propaga excepciones (fail-open).
"""

from __future__ import annotations

import json
import logging
import uuid
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode, TurnRole
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.reranker import FakeReranker
from app.llm.schemas import CompletionResult
from app.memory.config import MemoryConfigError, RetentionConfig
from app.memory.conversation_turns import ConversationTurnStore
from app.models.audit import AuditLog
from app.models.conversation_turn import ConversationTurn
from app.models.memory import EpisodicMemory
from app.models.session import ChatSession
from app.models.user import User
from app.schemas.conversation_turn import ConversationTurnCreate
from app.workflows.consolidation import (
    _async_consolidate_session,
    _load_retention_config_safe,
    consolidate_session,
)

USER_ID = str(uuid.uuid4())
SESSION_ID = str(uuid.uuid4())


def _make_llm_with_summary(summary: str, topics: dict | None = None) -> FakeLlmClient:
    """FakeLlmClient cuyo proximo ``complete`` devuelve un resumen JSON valido."""
    client = FakeLlmClient(served_models=frozenset({"qwen"}))
    client.queue_result(
        CompletionResult(
            text=json.dumps({"summary": summary, "topics": topics or {}}),
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=20,
            model_name="qwen",
            latency_ms=5.0,
        )
    )
    return client


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_session(
    session: AsyncSession, *, user_id: UUID, mode: Mode = Mode.VIDA
) -> ChatSession:
    cs = ChatSession(user_id=user_id, mode=mode)
    session.add(cs)
    await session.flush()
    await session.refresh(cs)
    return cs


async def _seed_turns(session: AsyncSession, *, user_id: UUID, session_id: UUID) -> None:
    """Siembra 2 turnos cifrados (user seq=0, model seq=1) via el store real."""
    store = ConversationTurnStore(session, user_id)
    await store.add(
        ConversationTurnCreate(
            session_id=session_id, role=TurnRole.USER, content="hola Ynara", seq=0
        )
    )
    await store.add(
        ConversationTurnCreate(
            session_id=session_id, role=TurnRole.MODEL, content="hola, en que te ayudo?", seq=1
        )
    )


# ---------------------------------------------------------------------------
# UNIT — wrapper Celery
# ---------------------------------------------------------------------------


class TestConsolidateSessionWrapper:
    """Tests del wrapper Celery ``consolidate_session``."""

    def test_task_name_is_correct(self) -> None:
        assert consolidate_session.name == "workflows.consolidate_session"

    def test_calls_async_with_correct_args(self) -> None:
        """El wrapper llama a ``_async_consolidate_session`` con los args correctos."""
        with patch(
            "app.workflows.consolidation._async_consolidate_session", new_callable=AsyncMock
        ) as mock_async:
            mock_async.return_value = 1
            consolidate_session(user_id=USER_ID, session_id=SESSION_ID, mode="bienestar")
            mock_async.assert_called_once_with(
                user_id=USER_ID, session_id=SESSION_ID, mode="bienestar"
            )

    def test_does_not_propagate_on_error(self) -> None:
        """Si el cuerpo async lanza, el wrapper NO propaga (fail-open)."""
        with patch(
            "app.workflows.consolidation._async_consolidate_session", new_callable=AsyncMock
        ) as mock_async:
            mock_async.side_effect = RuntimeError("DB caida")
            # No debe lanzar.
            consolidate_session(user_id=USER_ID, session_id=SESSION_ID, mode="vida")

    def test_returns_none_on_success(self) -> None:
        with patch(
            "app.workflows.consolidation._async_consolidate_session", new_callable=AsyncMock
        ) as mock_async:
            mock_async.return_value = 1
            result = consolidate_session(user_id=USER_ID, session_id=SESSION_ID, mode="vida")
        assert result is None


class TestLoadRetentionConfigSafe:
    """Tests del fallback defensivo ``_load_retention_config_safe`` (ADR-007 D2)."""

    def test_returns_loaded_config_when_valid(self) -> None:
        """Config valido -> el RetentionConfig cargado se devuelve tal cual."""
        with patch(
            "app.workflows.consolidation.load_retention_config",
            return_value=RetentionConfig(retention_default_days=200),
        ):
            cfg = _load_retention_config_safe()
        assert cfg.retention_default_days == 200

    def test_falls_back_to_defaults_on_invalid_config(self) -> None:
        """Config invalido (MemoryConfigError) -> defaults ADR-007 D2, NO crashea."""
        with patch(
            "app.workflows.consolidation.load_retention_config",
            side_effect=MemoryConfigError("config roto"),
        ):
            cfg = _load_retention_config_safe()
        # No propaga; cae a los defaults historicos (default=365, sensible=180).
        assert cfg == RetentionConfig()
        assert cfg.retention_default_days == 365
        assert cfg.retention_sensitive_days == 180


# ---------------------------------------------------------------------------
# UNIT — _async_consolidate_session con session inyectada (DB real via fixture)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAsyncConsolidateSession:
    """Tests de ``_async_consolidate_session`` contra la DB de tests (rollback)."""

    async def test_zero_turns_returns_zero_no_episode(self, db_session: AsyncSession) -> None:
        """0 turnos -> 0; NO se crea un episodio vacio."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        client = _make_llm_with_summary("no deberia usarse")

        created = await _async_consolidate_session(
            user_id=str(user.id),
            session_id=str(cs.id),
            mode="vida",
            llm_client=client,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            session=db_session,
        )
        assert created == 0
        count = (
            await db_session.execute(
                select(func.count())
                .select_from(EpisodicMemory)
                .where(EpisodicMemory.session_id == cs.id)
            )
        ).scalar_one()
        assert count == 0

    async def test_transcript_creates_one_episode(self, db_session: AsyncSession) -> None:
        """Con turnos, se crea exactamente 1 episodio con summary descifrado correcto."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        await _seed_turns(db_session, user_id=user.id, session_id=cs.id)
        client = _make_llm_with_summary("El usuario saludo y pidio ayuda.", {"temas": ["saludo"]})

        created = await _async_consolidate_session(
            user_id=str(user.id),
            session_id=str(cs.id),
            mode="vida",
            llm_client=client,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            session=db_session,
        )
        assert created == 1

        rows = list(
            (
                await db_session.execute(
                    select(EpisodicMemory).where(EpisodicMemory.session_id == cs.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        row = rows[0]
        # summary cifrado (bytes), embedding poblado.
        assert isinstance(row.summary, bytes)
        assert b"El usuario" not in row.summary
        assert row.summary_embedding is not None
        assert len(row.summary_embedding) == 1024
        assert row.is_sensitive is False
        assert row.retention_days == 365
        assert row.topics == {"temas": ["saludo"]}

        # Los turnos quedaron PURGADOS (summary + purge atomicos).
        turns_count = (
            await db_session.execute(
                select(func.count())
                .select_from(ConversationTurn)
                .where(ConversationTurn.session_id == cs.id)
            )
        ).scalar_one()
        assert turns_count == 0

    async def test_empty_summary_creates_no_episode(self, db_session: AsyncSession) -> None:
        """Qwen devuelve JSON corrupto -> parseo defensivo -> summary vacio -> 0 episodios.

        Ademas: los turnos NO se purgan (un reintento futuro podria resumir).
        """
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        await _seed_turns(db_session, user_id=user.id, session_id=cs.id)
        client = FakeLlmClient(served_models=frozenset({"qwen"}))
        client.queue_result(
            CompletionResult(
                text="esto no es json valido {",
                finish_reason="stop",
                prompt_tokens=5,
                completion_tokens=5,
                model_name="qwen",
                latency_ms=1.0,
            )
        )

        created = await _async_consolidate_session(
            user_id=str(user.id),
            session_id=str(cs.id),
            mode="vida",
            llm_client=client,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            session=db_session,
        )
        assert created == 0
        ep_count = (
            await db_session.execute(
                select(func.count())
                .select_from(EpisodicMemory)
                .where(EpisodicMemory.session_id == cs.id)
            )
        ).scalar_one()
        assert ep_count == 0
        # Turnos preservados para un reintento.
        turns_count = (
            await db_session.execute(
                select(func.count())
                .select_from(ConversationTurn)
                .where(ConversationTurn.session_id == cs.id)
            )
        ).scalar_one()
        assert turns_count == 2

    async def test_bienestar_is_sensitive_retention_capped(self, db_session: AsyncSession) -> None:
        """Modo Bienestar -> is_sensitive=True, retention_days <= 365 (ADR-007 D2)."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id, mode=Mode.BIENESTAR)
        await _seed_turns(db_session, user_id=user.id, session_id=cs.id)
        client = _make_llm_with_summary("Sesion de bienestar del usuario.")

        created = await _async_consolidate_session(
            user_id=str(user.id),
            session_id=str(cs.id),
            mode="bienestar",
            llm_client=client,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            session=db_session,
        )
        assert created == 1
        row = (
            await db_session.execute(
                select(EpisodicMemory).where(EpisodicMemory.session_id == cs.id)
            )
        ).scalar_one()
        assert row.is_sensitive is True
        assert 1 <= row.retention_days <= 365

    async def test_default_retention_from_injected_config(self, db_session: AsyncSession) -> None:
        """Un RetentionConfig inyectado cambia el ``retention_days`` default usado (ADR-007 D2).

        Verifica el cableado config-driven: si se inyecta un config con
        ``retention_default_days`` distinto del historico (365), el episodio NO
        sensible se persiste con ESE valor, no con el hardcodeado.
        """
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        await _seed_turns(db_session, user_id=user.id, session_id=cs.id)
        client = _make_llm_with_summary("Sesion no sensible con retention custom.")

        created = await _async_consolidate_session(
            user_id=str(user.id),
            session_id=str(cs.id),
            mode="vida",
            llm_client=client,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            retention_config=RetentionConfig(retention_default_days=200),
            session=db_session,
        )
        assert created == 1
        row = (
            await db_session.execute(
                select(EpisodicMemory).where(EpisodicMemory.session_id == cs.id)
            )
        ).scalar_one()
        assert row.is_sensitive is False
        assert row.retention_days == 200

    async def test_sensitive_retention_from_injected_config(self, db_session: AsyncSession) -> None:
        """Un RetentionConfig inyectado cambia el ``retention_days`` sensible (ADR-007 D2).

        Modo Bienestar -> is_sensitive=True -> usa ``retention_sensitive_days`` del
        config inyectado (90), no el historico (180).
        """
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id, mode=Mode.BIENESTAR)
        await _seed_turns(db_session, user_id=user.id, session_id=cs.id)
        client = _make_llm_with_summary("Sesion sensible con retention custom.")

        created = await _async_consolidate_session(
            user_id=str(user.id),
            session_id=str(cs.id),
            mode="bienestar",
            llm_client=client,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            retention_config=RetentionConfig(retention_sensitive_days=90),
            session=db_session,
        )
        assert created == 1
        row = (
            await db_session.execute(
                select(EpisodicMemory).where(EpisodicMemory.session_id == cs.id)
            )
        ).scalar_one()
        assert row.is_sensitive is True
        assert row.retention_days == 90

    async def test_default_config_matches_historic_values(self, db_session: AsyncSession) -> None:
        """Sin inyectar config, los defaults del loader = los valores historicos (180/365).

        Garantia de no-cambio-de-comportamiento: el ``RetentionConfig()`` por
        defaults espeja las constantes que estaban hardcodeadas (default=365,
        sensible=180), asi que una sesion sensible sin config custom sigue dando 180.
        """
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id, mode=Mode.BIENESTAR)
        await _seed_turns(db_session, user_id=user.id, session_id=cs.id)
        client = _make_llm_with_summary("Sesion sensible con defaults.")

        created = await _async_consolidate_session(
            user_id=str(user.id),
            session_id=str(cs.id),
            mode="bienestar",
            llm_client=client,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            retention_config=RetentionConfig(),  # defaults explicitos
            session=db_session,
        )
        assert created == 1
        row = (
            await db_session.execute(
                select(EpisodicMemory).where(EpisodicMemory.session_id == cs.id)
            )
        ).scalar_one()
        assert row.retention_days == 180

    async def test_idempotent_double_consolidation(self, db_session: AsyncSession) -> None:
        """Consolidar dos veces -> 1 episodio (la 2da es no-op por idempotencia)."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        await _seed_turns(db_session, user_id=user.id, session_id=cs.id)

        first = await _async_consolidate_session(
            user_id=str(user.id),
            session_id=str(cs.id),
            mode="vida",
            llm_client=_make_llm_with_summary("Resumen uno."),
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            session=db_session,
        )
        assert first == 1

        # Segunda corrida: los turnos ya se purgaron y el episodio existe -> no-op.
        second = await _async_consolidate_session(
            user_id=str(user.id),
            session_id=str(cs.id),
            mode="vida",
            llm_client=_make_llm_with_summary("Resumen dos."),
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            session=db_session,
        )
        assert second == 0

        count = (
            await db_session.execute(
                select(func.count())
                .select_from(EpisodicMemory)
                .where(EpisodicMemory.session_id == cs.id)
            )
        ).scalar_one()
        assert count == 1

    async def test_audit_log_one_write_episodic_row(self, db_session: AsyncSession) -> None:
        """Crear un episodio escribe 1 fila WRITE/EPISODIC en audit_log con origin QWEN."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        await _seed_turns(db_session, user_id=user.id, session_id=cs.id)

        created = await _async_consolidate_session(
            user_id=str(user.id),
            session_id=str(cs.id),
            mode="vida",
            llm_client=_make_llm_with_summary("Resumen auditable."),
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            session=db_session,
        )
        assert created == 1

        rows = list(
            (await db_session.execute(select(AuditLog).where(AuditLog.user_id == user.id)))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        audit = rows[0]
        assert audit.operation == AuditOperation.WRITE
        assert audit.target_layer == MemoryLayer.EPISODIC
        assert audit.origin_model == LlmModel.QWEN
        # record_hash es un sha256 hex (64 chars), NUNCA el summary en claro.
        assert len(audit.record_hash) == 64

    async def test_integrity_error_race_degrades_to_zero(self, db_session: AsyncSession) -> None:
        """Carrera entre workers: si ``episodic_store.add`` tira ``IntegrityError`` (la
        UNIQUE(session_id) la rechaza porque otro worker insertó entre el SELECT y el
        INSERT), se degrada a 0 (no-op) SIN propagar y sin duplicar.

        Es la rama de la red final de idempotencia (consolidation.py:426-437): el
        chequeo previo ``_episode_exists`` no alcanza ante la carrera, así que el
        ``IntegrityError`` del INSERT se atrapa, se hace ``rollback`` del estado parcial
        y se retorna 0. Se fuerza el ``IntegrityError`` parcheando ``add`` del store
        (el momento exacto de la carrera no se puede orquestar de forma determinista).
        """
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        await _seed_turns(db_session, user_id=user.id, session_id=cs.id)
        client = _make_llm_with_summary("Resumen que choca con la UNIQUE.")

        # Forzar el IntegrityError de la UNIQUE(session_id) al insertar el episodio:
        # simula que otro worker ganó la carrera entre el SELECT y este INSERT.
        boom = IntegrityError("INSERT ...", params=None, orig=Exception("UNIQUE session_id"))
        with patch(
            "app.workflows.consolidation.EpisodicMemoryStore.add",
            new_callable=AsyncMock,
            side_effect=boom,
        ):
            created = await _async_consolidate_session(
                user_id=str(user.id),
                session_id=str(cs.id),
                mode="vida",
                llm_client=client,
                embedder=FakeEmbeddingClient(),
                reranker=FakeReranker(),
                session=db_session,
            )

        # La rama IntegrityError degrada a 0 (no-op): no se propaga la excepción.
        assert created == 0
        # No se creó episodio (el INSERT falló y se revirtió).
        ep_count = (
            await db_session.execute(
                select(func.count())
                .select_from(EpisodicMemory)
                .where(EpisodicMemory.session_id == cs.id)
            )
        ).scalar_one()
        assert ep_count == 0

    async def test_garbage_session_id_returns_zero(self, db_session: AsyncSession) -> None:
        """Un session_id no-UUID degrada a 0 (no-op) sin crashear."""
        user = await _seed_user(db_session)
        created = await _async_consolidate_session(
            user_id=str(user.id),
            session_id="no-soy-un-uuid",
            mode="vida",
            llm_client=_make_llm_with_summary("no deberia usarse"),
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            session=db_session,
        )
        assert created == 0

    async def test_no_pii_in_logs(
        self, db_session: AsyncSession, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Los logs de la consolidacion NO contienen el contenido del usuario (regla #4)."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        secret_user = "informacion ultra confidencial del usuario 42"
        secret_model = "respuesta sensible del asistente"
        store = ConversationTurnStore(db_session, user.id)
        await store.add(
            ConversationTurnCreate(session_id=cs.id, role=TurnRole.USER, content=secret_user, seq=0)
        )
        await store.add(
            ConversationTurnCreate(
                session_id=cs.id, role=TurnRole.MODEL, content=secret_model, seq=1
            )
        )

        with caplog.at_level(logging.DEBUG, logger="app.workflows.consolidation"):
            created = await _async_consolidate_session(
                user_id=str(user.id),
                session_id=str(cs.id),
                mode="vida",
                llm_client=_make_llm_with_summary("Resumen sin filtrar PII."),
                embedder=FakeEmbeddingClient(),
                reranker=FakeReranker(),
                session=db_session,
            )
        assert created == 1
        full_log = caplog.text
        assert secret_user not in full_log
        assert secret_model not in full_log
