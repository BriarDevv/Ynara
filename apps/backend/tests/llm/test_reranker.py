"""Contract tests del Reranker Protocol + determinismo del FakeReranker.

Sin red ni GPU: el fake es passthrough determinista. Estos tests blindan el
contrato que consume la capa de memoria (M7) cuando reordena los candidatos
ANN antes de construir los schemas Out.
"""

from __future__ import annotations

import pytest

from app.llm.clients.reranker import FakeReranker, Reranker, RerankResult

# ---------- conformance al Protocol ----------


def test_fake_conforms_to_protocol() -> None:
    # runtime_checkable: el fake satisface el Protocol por duck typing.
    assert isinstance(FakeReranker(), Reranker)


# ---------- passthrough preserva orden ----------


async def test_rerank_passthrough_preserves_input_order() -> None:
    """El FakeReranker devuelve los documentos en el mismo orden de entrada."""
    fake = FakeReranker()
    docs = ["doc A", "doc B", "doc C"]
    results = await fake.rerank(query="q", documents=docs)

    assert len(results) == 3
    assert [r.index for r in results] == [0, 1, 2]


async def test_rerank_scores_are_descending() -> None:
    """Los scores asignados son estrictamente decrecientes (el primero es el mejor)."""
    fake = FakeReranker()
    docs = ["uno", "dos", "tres", "cuatro"]
    results = await fake.rerank(query="q", documents=docs)

    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


async def test_rerank_scores_are_deterministic() -> None:
    """Misma entrada → mismos scores en cualquier llamada."""
    fake = FakeReranker()
    docs = ["x", "y"]
    first = await fake.rerank(query="q", documents=docs)
    second = await fake.rerank(query="q", documents=docs)

    assert first == second


async def test_rerank_scores_deterministic_across_instances() -> None:
    """El determinismo no depende del estado de instancia."""
    docs = ["a", "b", "c"]
    r1 = await FakeReranker().rerank(query="q", documents=docs)
    r2 = await FakeReranker().rerank(query="q", documents=docs)
    assert r1 == r2


# ---------- top_n recorta ----------


async def test_rerank_top_n_truncates_results() -> None:
    """top_n recorta la lista al número pedido."""
    fake = FakeReranker()
    docs = ["a", "b", "c", "d", "e"]
    results = await fake.rerank(query="q", documents=docs, top_n=3)

    assert len(results) == 3


async def test_rerank_top_n_keeps_best_first() -> None:
    """top_n conserva los primeros (mejores scored) del passthrough."""
    fake = FakeReranker()
    docs = ["a", "b", "c", "d"]
    results = await fake.rerank(query="q", documents=docs, top_n=2)

    assert [r.index for r in results] == [0, 1]


async def test_rerank_top_n_none_returns_all() -> None:
    """top_n=None (default) devuelve todos los documentos."""
    fake = FakeReranker()
    docs = ["uno", "dos", "tres"]
    results = await fake.rerank(query="q", documents=docs, top_n=None)

    assert len(results) == len(docs)


async def test_rerank_top_n_larger_than_docs_returns_all() -> None:
    """top_n mayor que len(documents) devuelve todos (no error)."""
    fake = FakeReranker()
    docs = ["solo", "dos"]
    results = await fake.rerank(query="q", documents=docs, top_n=100)

    assert len(results) == 2


# ---------- casos borde ----------


async def test_rerank_empty_documents() -> None:
    """Lista vacía → resultado vacío, sin error."""
    results = await FakeReranker().rerank(query="q", documents=[])
    assert results == []


async def test_rerank_single_document() -> None:
    """Un solo documento → un RerankResult con index=0."""
    [result] = await FakeReranker().rerank(query="q", documents=["solo"])
    assert result.index == 0
    assert result.score == pytest.approx(1.0)


async def test_rerank_result_is_frozen_dataclass() -> None:
    """RerankResult es inmutable (frozen dataclass)."""
    r = RerankResult(index=0, score=1.0)
    with pytest.raises((AttributeError, TypeError)):
        r.score = 0.5  # type: ignore[misc]


# ---------- registro de llamadas ----------


async def test_rerank_calls_are_recorded() -> None:
    """rerank_calls acumula los argumentos de cada invocación."""
    fake = FakeReranker()
    await fake.rerank(query="primera", documents=["a", "b"])
    await fake.rerank(query="segunda", documents=["c"], top_n=1)

    assert len(fake.rerank_calls) == 2
    assert fake.rerank_calls[0]["query"] == "primera"
    assert fake.rerank_calls[0]["documents"] == ["a", "b"]
    assert fake.rerank_calls[0]["top_n"] is None
    assert fake.rerank_calls[1]["query"] == "segunda"
    assert fake.rerank_calls[1]["top_n"] == 1


# ---------- health ----------


async def test_health_reports_healthy_by_default() -> None:
    health = await FakeReranker().health()
    assert health.healthy is True
    assert health.model_name == "fake-reranker"


async def test_health_can_be_forced_unhealthy() -> None:
    fake = FakeReranker()
    fake.set_health(False)
    assert (await fake.health()).healthy is False


async def test_health_custom_model_name() -> None:
    health = await FakeReranker(model="cross-encoder-v1").health()
    assert health.model_name == "cross-encoder-v1"
