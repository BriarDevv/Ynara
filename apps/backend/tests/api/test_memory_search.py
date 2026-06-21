"""Tests de ``GET /v1/memory/search``.

Dos niveles:
- **Unitarios** (sin DB, suite default): ``_build_search_response`` (mapeo de capas
  + orden + ``score`` por rank) y ``_rank_score`` (decaimiento con floor). Cubren la
  lógica de presentación, que es la parte propia de este endpoint.
- **Integration** (``@pytest.mark.integration``, DB de tests): smoke del endpoint —
  401 sin token, query en blanco → 200 vacío, user sin memoria → 200 vacío. La
  búsqueda real (ANN + rerank) ya está cubierta por los tests de los stores; acá
  solo se verifica el wiring + aislamiento por auth. Fakes de embedder/reranker
  overrideados (el lifespan no corre bajo ASGITransport).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_embedder, get_reranker
from app.core.security import create_access_token
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.reranker import FakeReranker
from app.main import app
from app.models.user import User
from app.schemas.memory import EpisodicMemoryOut, SemanticMemoryOut
from app.services.memory import _build_search_response, _rank_score

_T = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _sem(content: str) -> SemanticMemoryOut:
    return SemanticMemoryOut(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        content=content,
        importance=None,
        source_session_id=None,
        created_at=_T,
        updated_at=_T,
    )


def _epi(summary: str, occurred_at: datetime) -> EpisodicMemoryOut:
    return EpisodicMemoryOut(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        summary=summary,
        is_sensitive=False,
        retention_days=365,
        occurred_at=occurred_at,
        topics={},
        created_at=_T,
        updated_at=_T,
    )


# ---------- unitarios (lógica pura) ----------


def test_rank_score_decreases_with_floor() -> None:
    assert _rank_score(0) == pytest.approx(0.95)
    assert _rank_score(1) == pytest.approx(0.87)
    assert _rank_score(100) == 0.5  # floor
    assert all(0.0 <= _rank_score(i) <= 1.0 for i in range(20))


def test_build_search_response_maps_layers_order_and_score() -> None:
    sem = [_sem("hecho uno"), _sem("hecho dos")]
    epi_at = datetime(2026, 2, 1, tzinfo=UTC)
    epi = [_epi("momento uno", epi_at)]

    resp = _build_search_response("tesis", sem, epi)

    assert resp.query == "tesis"
    assert resp.total == 3
    # Orden: semantic primero, episodic después.
    assert [h.layer.value for h in resp.results] == ["semantic", "semantic", "episodic"]
    # Mapeo de campos.
    assert resp.results[0].ref == str(sem[0].id)
    assert resp.results[0].snippet == "hecho uno"
    assert resp.results[0].occurred_at == _T  # created_at del semantic
    assert resp.results[2].snippet == "momento uno"
    assert resp.results[2].occurred_at == epi_at
    # Score decreciente por posición combinada.
    assert resp.results[0].score == pytest.approx(0.95)
    assert resp.results[1].score == pytest.approx(0.87)
    assert resp.results[2].score == pytest.approx(0.79)


def test_build_search_response_empty() -> None:
    resp = _build_search_response("x", [], [])
    assert resp.total == 0
    assert resp.results == []


# ---------- integration (smoke del endpoint) ----------


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession) -> httpx.AsyncClient:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_embedder] = lambda: FakeEmbeddingClient()
    app.dependency_overrides[get_reranker] = lambda: FakeReranker()
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.integration
async def test_search_requires_auth(db_session: AsyncSession) -> None:
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/memory/search?q=tesis")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
async def test_search_blank_query_returns_empty(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/memory/search?q=%20%20", headers=_bearer(user.id))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["results"] == []
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
async def test_search_fresh_user_returns_empty(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/memory/search?q=tesis", headers=_bearer(user.id))
        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "tesis"
        assert body["total"] == 0
    finally:
        app.dependency_overrides.clear()
