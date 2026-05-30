"""Contract test del EmbeddingClient + determinismo del FakeEmbeddingClient.

Sin red ni GPU: el fake produce vectores deterministas. Estos tests blindan el
contrato que consumen los wrappers de memoria (M7) y el router (M8).
"""

from __future__ import annotations

from app.llm.clients.embedding import EMBEDDING_DIM, EmbeddingClient, FakeEmbeddingClient


def test_fake_conforms_to_protocol() -> None:
    # runtime_checkable: el fake satisface el Protocol por duck typing.
    assert isinstance(FakeEmbeddingClient(), EmbeddingClient)


async def test_embed_dimension_is_1024() -> None:
    [vector] = await FakeEmbeddingClient().embed(["un hecho"])
    assert len(vector) == EMBEDDING_DIM


async def test_embed_is_deterministic() -> None:
    fake = FakeEmbeddingClient()
    first = await fake.embed(["mismo texto"])
    second = await fake.embed(["mismo texto"])
    assert first == second


async def test_distinct_texts_give_distinct_vectors() -> None:
    fake = FakeEmbeddingClient()
    [a], [b] = await fake.embed(["texto A"]), await fake.embed(["texto B"])
    assert a != b


async def test_embed_batch_preserves_order_and_count() -> None:
    fake = FakeEmbeddingClient()
    texts = ["uno", "dos", "tres"]
    vectors = await fake.embed(texts)
    assert len(vectors) == 3
    # El vector de cada texto coincide con el de su embed individual (orden estable).
    for text, vector in zip(texts, vectors, strict=True):
        [solo] = await fake.embed([text])
        assert vector == solo


async def test_values_in_unit_range() -> None:
    [vector] = await FakeEmbeddingClient().embed(["rango"])
    assert all(-1.0 <= value <= 1.0 for value in vector)


async def test_empty_batch_returns_empty() -> None:
    assert await FakeEmbeddingClient().embed([]) == []


async def test_custom_dim() -> None:
    [vector] = await FakeEmbeddingClient(dim=8).embed(["chico"])
    assert len(vector) == 8


async def test_health_reports_healthy_by_default() -> None:
    health = await FakeEmbeddingClient().health()
    assert health.healthy is True
    assert health.model_name == "bge-m3"


async def test_health_can_be_forced_unhealthy() -> None:
    fake = FakeEmbeddingClient()
    fake.set_health(False)
    assert (await fake.health()).healthy is False


async def test_embed_calls_are_recorded() -> None:
    fake = FakeEmbeddingClient()
    await fake.embed(["a", "b"])
    assert fake.embed_calls == [["a", "b"]]
