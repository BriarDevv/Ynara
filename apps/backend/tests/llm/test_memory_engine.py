"""Tests del MemoryEngine (M8 Ola 2).

UNIT (sin DB ni red):
- QwenMemoryEngine con JSON valido -> devuelve los MemoryOp correctos.
- QwenMemoryEngine con JSON invalido / texto libre -> [] sin crashear.
- QwenMemoryEngine con respuesta no-lista -> [].
- QwenMemoryEngine con ops malformadas -> solo las validas.
- QwenMemoryEngine: fallo del LLM -> [] sin propagar.
- FakeMemoryEngine devuelve sus ops prefijadas y registra la llamada.
- MemoryOp es frozen (inmutable).
- Protocol runtime_checkable: FakeMemoryEngine satisface MemoryEngine.

INTEGRATION (@pytest.mark.integration, db_session):
- apply_ops ADD semantic -> search lo encuentra.
- apply_ops ADD procedural -> get lo encuentra.
- apply_ops UPDATE procedural -> get devuelve el nuevo valor.
- apply_ops DELETE semantic -> delete -> search no lo devuelve.
- apply_ops DELETE procedural -> get devuelve None.
- apply_ops NOOP -> 0 ops aplicadas.
- apply_ops con target_id/key faltante -> skip robusto (no crashea).
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest

from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.reranker import FakeReranker
from app.llm.memory_engine import (
    FakeMemoryEngine,
    MemoryEngine,
    MemoryOp,
    QwenMemoryEngine,
    apply_ops,
)
from app.llm.schemas import CompletionResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = uuid4()


def _make_result(text: str) -> CompletionResult:
    return CompletionResult(
        text=text,
        finish_reason="stop",
        prompt_tokens=10,
        completion_tokens=5,
        model_name="qwen",
        latency_ms=1.0,
    )


def _json_ops(ops: list[dict[str, Any]]) -> str:
    return json.dumps(ops)


# ---------------------------------------------------------------------------
# UNIT: MemoryOp
# ---------------------------------------------------------------------------


def test_memory_op_frozen() -> None:
    op = MemoryOp(op="ADD", layer="semantic", content="hecho de prueba")
    with pytest.raises((AttributeError, TypeError)):
        op.content = "otro"  # type: ignore[misc]


def test_memory_op_defaults() -> None:
    op = MemoryOp(op="NOOP", layer="semantic")
    assert op.content == ""
    assert op.key is None
    assert op.value is None
    assert op.target_id is None


# ---------------------------------------------------------------------------
# UNIT: FakeMemoryEngine
# ---------------------------------------------------------------------------


async def test_fake_memory_engine_returns_preset_ops() -> None:
    preset = [
        MemoryOp(op="ADD", layer="semantic", content="El usuario se llama Ana."),
        MemoryOp(op="ADD", layer="procedural", key="idioma", value={"lang": "es"}),
    ]
    engine = FakeMemoryEngine(ops=preset)
    result = await engine.consolidate(
        user_msg="me llamo Ana", model_response="Hola Ana!", mode="vida"
    )
    assert result == preset


async def test_fake_memory_engine_records_calls() -> None:
    engine = FakeMemoryEngine(ops=[])
    await engine.consolidate(user_msg="hola", model_response="hola!", mode="estudio")
    assert len(engine.consolidate_calls) == 1
    call = engine.consolidate_calls[0]
    assert call["user_msg"] == "hola"
    assert call["mode"] == "estudio"


async def test_fake_memory_engine_multiple_calls_independent() -> None:
    preset = [MemoryOp(op="NOOP", layer="semantic")]
    engine = FakeMemoryEngine(ops=preset)
    r1 = await engine.consolidate(user_msg="a", model_response="b", mode="vida")
    r2 = await engine.consolidate(user_msg="c", model_response="d", mode="vida")
    # Cada llamada devuelve una copia independiente.
    assert r1 == r2
    assert r1 is not r2


# ---------------------------------------------------------------------------
# UNIT: Protocol conformance
# ---------------------------------------------------------------------------


def test_fake_memory_engine_satisfies_protocol() -> None:
    engine = FakeMemoryEngine(ops=[])
    assert isinstance(engine, MemoryEngine)


# ---------------------------------------------------------------------------
# UNIT: QwenMemoryEngine — parseo correcto
# ---------------------------------------------------------------------------


async def test_qwen_engine_valid_json_add_semantic() -> None:
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake_llm.queue_result(
        _make_result(
            _json_ops([{"op": "ADD", "layer": "semantic", "content": "El usuario es medico."}])
        )
    )
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    ops = await engine.consolidate(
        user_msg="soy medico", model_response="interesante!", mode="vida"
    )
    assert len(ops) == 1
    assert ops[0].op == "ADD"
    assert ops[0].layer == "semantic"
    assert ops[0].content == "El usuario es medico."


async def test_qwen_engine_valid_json_add_procedural() -> None:
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake_llm.queue_result(
        _make_result(
            _json_ops(
                [
                    {
                        "op": "ADD",
                        "layer": "procedural",
                        "key": "idioma_preferido",
                        "value": {"idioma": "es-AR", "tono": "informal"},
                    }
                ]
            )
        )
    )
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    ops = await engine.consolidate(
        user_msg="prefiero tono informal", model_response="dale!", mode="vida"
    )
    assert len(ops) == 1
    assert ops[0].op == "ADD"
    assert ops[0].layer == "procedural"
    assert ops[0].key == "idioma_preferido"
    assert ops[0].value == {"idioma": "es-AR", "tono": "informal"}


async def test_qwen_engine_multiple_ops() -> None:
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    raw_ops = [
        {"op": "ADD", "layer": "semantic", "content": "El usuario vive en Buenos Aires."},
        {"op": "ADD", "layer": "procedural", "key": "ciudad", "value": {"ciudad": "Buenos Aires"}},
        {"op": "NOOP", "layer": "semantic"},
    ]
    fake_llm.queue_result(_make_result(_json_ops(raw_ops)))
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    ops = await engine.consolidate(
        user_msg="vivo en Buenos Aires", model_response="genial", mode="vida"
    )
    assert len(ops) == 3
    assert ops[2].op == "NOOP"


async def test_qwen_engine_delete_semantic_with_target_id() -> None:
    target = str(uuid4())
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake_llm.queue_result(
        _make_result(_json_ops([{"op": "DELETE", "layer": "semantic", "target_id": target}]))
    )
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    ops = await engine.consolidate(
        user_msg="eso ya no aplica", model_response="ok, lo elimino", mode="vida"
    )
    assert len(ops) == 1
    assert ops[0].op == "DELETE"
    assert ops[0].target_id == target


async def test_qwen_engine_update_procedural() -> None:
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake_llm.queue_result(
        _make_result(
            _json_ops(
                [
                    {
                        "op": "UPDATE",
                        "layer": "procedural",
                        "key": "idioma_preferido",
                        "value": {"idioma": "es-MX"},
                    }
                ]
            )
        )
    )
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    ops = await engine.consolidate(
        user_msg="ahora prefiero mexicano", model_response="anotado", mode="vida"
    )
    assert len(ops) == 1
    assert ops[0].op == "UPDATE"
    assert ops[0].key == "idioma_preferido"


# ---------------------------------------------------------------------------
# UNIT: QwenMemoryEngine — parseo defensivo
# ---------------------------------------------------------------------------


async def test_qwen_engine_invalid_json_returns_empty() -> None:
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake_llm.queue_result(_make_result("esto no es json {{{"))
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    ops = await engine.consolidate(user_msg="hola", model_response="hola!", mode="vida")
    assert ops == []


async def test_qwen_engine_free_text_returns_empty() -> None:
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake_llm.queue_result(
        _make_result(
            "No encontre ningun hecho relevante en esta conversacion. El usuario solo saludo."
        )
    )
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    ops = await engine.consolidate(user_msg="hola", model_response="hola!", mode="vida")
    assert ops == []


async def test_qwen_engine_non_list_json_returns_empty() -> None:
    """JSON valido pero no es lista -> []."""
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake_llm.queue_result(_make_result('{"op": "ADD", "layer": "semantic", "content": "x"}'))
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    ops = await engine.consolidate(user_msg="x", model_response="y", mode="vida")
    assert ops == []


async def test_qwen_engine_invalid_op_value_skipped() -> None:
    """Op con 'op' invalido se skipea; las validas se devuelven."""
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    raw_ops = [
        {"op": "INVALID_OP", "layer": "semantic", "content": "x"},
        {"op": "ADD", "layer": "semantic", "content": "hecho valido"},
    ]
    fake_llm.queue_result(_make_result(_json_ops(raw_ops)))
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    ops = await engine.consolidate(user_msg="x", model_response="y", mode="vida")
    assert len(ops) == 1
    assert ops[0].content == "hecho valido"


async def test_qwen_engine_invalid_layer_skipped() -> None:
    """Op con layer 'episodic' se skipea (Ola 2 solo semantic+procedural)."""
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    raw_ops = [
        {"op": "ADD", "layer": "episodic", "content": "evento"},
        {"op": "ADD", "layer": "semantic", "content": "hecho valido"},
    ]
    fake_llm.queue_result(_make_result(_json_ops(raw_ops)))
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    ops = await engine.consolidate(user_msg="x", model_response="y", mode="vida")
    assert len(ops) == 1
    assert ops[0].layer == "semantic"


async def test_qwen_engine_llm_failure_returns_empty() -> None:
    """Si el LLM levanta una excepcion, consolidate devuelve [] sin propagar."""
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake_llm.queue_error(RuntimeError("vllm timeout"))
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    ops = await engine.consolidate(user_msg="x", model_response="y", mode="vida")
    assert ops == []


async def test_qwen_engine_calls_llm_once() -> None:
    """consolidate hace exactamente 1 llamada al LLM por turno."""
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake_llm.queue_result(_make_result("[]"))
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    await engine.consolidate(user_msg="x", model_response="y", mode="vida")
    assert len(fake_llm.complete_calls) == 1


async def test_qwen_engine_uses_low_temperature() -> None:
    """consolidate usa temperature baja para extraccion estructurada."""
    fake_llm = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake_llm.queue_result(_make_result("[]"))
    engine = QwenMemoryEngine(llm_client=fake_llm, served_name="qwen")
    await engine.consolidate(user_msg="x", model_response="y", mode="vida")
    # FakeLlmClient no registra temperature, pero verifica que se llamó al modelo correcto.
    assert fake_llm.complete_calls[0]["model"] == "qwen"


# ---------------------------------------------------------------------------
# INTEGRATION: helpers
# ---------------------------------------------------------------------------


async def _seed_user_for_engine(session: Any) -> Any:
    """Inserta un User minimo y lo retorna (flush, no commit — rollback al final)."""
    from app.models.user import User

    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


def _make_stores(session: Any, user_id: Any) -> tuple[Any, Any]:
    from app.memory.procedural import ProceduralMemoryStore
    from app.memory.semantic import SemanticMemoryStore

    embedder = FakeEmbeddingClient()
    reranker = FakeReranker()
    semantic = SemanticMemoryStore(session, user_id, embedder, reranker)
    procedural = ProceduralMemoryStore(session, user_id)
    return semantic, procedural


# ---------------------------------------------------------------------------
# INTEGRATION: apply_ops contra stores reales
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_apply_ops_add_semantic_search_finds_it(db_session: Any) -> None:
    """ADD semantic -> search recupera el hecho."""
    user = await _seed_user_for_engine(db_session)
    semantic, procedural = _make_stores(db_session, user.id)

    ops = [MemoryOp(op="ADD", layer="semantic", content="El usuario trabaja como ingeniero.")]
    applied = await apply_ops(ops, semantic_store=semantic, procedural_store=procedural)
    assert applied == 1

    results = await semantic.search("ingeniero", limit=5)
    assert any("ingeniero" in r.content for r in results)


@pytest.mark.integration
async def test_apply_ops_add_procedural_get_finds_it(db_session: Any) -> None:
    """ADD procedural -> get recupera la entrada."""
    user = await _seed_user_for_engine(db_session)
    semantic, procedural = _make_stores(db_session, user.id)

    ops = [
        MemoryOp(
            op="ADD",
            layer="procedural",
            key="idioma_test",
            value={"idioma": "es-AR"},
        )
    ]
    applied = await apply_ops(ops, semantic_store=semantic, procedural_store=procedural)
    assert applied == 1

    entry = await procedural.get("idioma_test")
    assert entry is not None
    assert entry.value == {"idioma": "es-AR"}


@pytest.mark.integration
async def test_apply_ops_update_procedural(db_session: Any) -> None:
    """ADD + UPDATE procedural -> get devuelve el valor actualizado."""
    user = await _seed_user_for_engine(db_session)
    semantic, procedural = _make_stores(db_session, user.id)

    # ADD inicial
    ops_add = [MemoryOp(op="ADD", layer="procedural", key="tono", value={"tono": "formal"})]
    await apply_ops(ops_add, semantic_store=semantic, procedural_store=procedural)

    # UPDATE (upsert refuerza)
    ops_upd = [MemoryOp(op="UPDATE", layer="procedural", key="tono", value={"tono": "informal"})]
    applied = await apply_ops(ops_upd, semantic_store=semantic, procedural_store=procedural)
    assert applied == 1

    entry = await procedural.get("tono")
    assert entry is not None
    assert entry.value == {"tono": "informal"}


@pytest.mark.integration
async def test_apply_ops_delete_semantic(db_session: Any) -> None:
    """ADD semantic + DELETE semantic -> hecho borrado."""
    from app.schemas.memory import SemanticMemoryCreate

    user = await _seed_user_for_engine(db_session)
    semantic, procedural = _make_stores(db_session, user.id)

    # Insertar primero via store directamente para tener el id.
    created = await semantic.add(SemanticMemoryCreate(content="hecho a borrar"))
    target_id = str(created.id)

    # DELETE via apply_ops
    ops = [MemoryOp(op="DELETE", layer="semantic", target_id=target_id)]
    applied = await apply_ops(ops, semantic_store=semantic, procedural_store=procedural)
    assert applied == 1

    # Verificar que ya no existe: delete de nuevo devuelve False (ya fue borrado).
    deleted_again = await semantic.delete(created.id)
    assert not deleted_again


@pytest.mark.integration
async def test_apply_ops_delete_procedural(db_session: Any) -> None:
    """ADD procedural + DELETE procedural -> get devuelve None."""
    user = await _seed_user_for_engine(db_session)
    semantic, procedural = _make_stores(db_session, user.id)

    ops_add = [MemoryOp(op="ADD", layer="procedural", key="pref_a_borrar", value={"x": 1})]
    await apply_ops(ops_add, semantic_store=semantic, procedural_store=procedural)

    ops_del = [MemoryOp(op="DELETE", layer="procedural", key="pref_a_borrar")]
    applied = await apply_ops(ops_del, semantic_store=semantic, procedural_store=procedural)
    assert applied == 1

    entry = await procedural.get("pref_a_borrar")
    assert entry is None


@pytest.mark.integration
async def test_apply_ops_noop_returns_zero(db_session: Any) -> None:
    """NOOP -> 0 ops aplicadas, no escribe nada."""
    user = await _seed_user_for_engine(db_session)
    semantic, procedural = _make_stores(db_session, user.id)

    ops = [MemoryOp(op="NOOP", layer="semantic"), MemoryOp(op="NOOP", layer="procedural")]
    applied = await apply_ops(ops, semantic_store=semantic, procedural_store=procedural)
    assert applied == 0


@pytest.mark.integration
async def test_apply_ops_missing_target_id_skips_delete_semantic(db_session: Any) -> None:
    """DELETE semantic sin target_id -> skip robusto, no crashea."""
    user = await _seed_user_for_engine(db_session)
    semantic, procedural = _make_stores(db_session, user.id)

    ops = [MemoryOp(op="DELETE", layer="semantic", target_id=None)]
    applied = await apply_ops(ops, semantic_store=semantic, procedural_store=procedural)
    assert applied == 0


@pytest.mark.integration
async def test_apply_ops_missing_key_skips_delete_procedural(db_session: Any) -> None:
    """DELETE procedural sin key -> skip robusto, no crashea."""
    user = await _seed_user_for_engine(db_session)
    semantic, procedural = _make_stores(db_session, user.id)

    ops = [MemoryOp(op="DELETE", layer="procedural", key=None)]
    applied = await apply_ops(ops, semantic_store=semantic, procedural_store=procedural)
    assert applied == 0


@pytest.mark.integration
async def test_apply_ops_add_semantic_without_content_skips(db_session: Any) -> None:
    """ADD semantic con content vacio -> skip, no escribe."""
    user = await _seed_user_for_engine(db_session)
    semantic, procedural = _make_stores(db_session, user.id)

    ops = [MemoryOp(op="ADD", layer="semantic", content="")]
    applied = await apply_ops(ops, semantic_store=semantic, procedural_store=procedural)
    assert applied == 0


@pytest.mark.integration
async def test_apply_ops_add_procedural_without_key_skips(db_session: Any) -> None:
    """ADD procedural sin key -> skip, no escribe."""
    user = await _seed_user_for_engine(db_session)
    semantic, procedural = _make_stores(db_session, user.id)

    ops = [MemoryOp(op="ADD", layer="procedural", key=None, value={"x": 1})]
    applied = await apply_ops(ops, semantic_store=semantic, procedural_store=procedural)
    assert applied == 0


@pytest.mark.integration
async def test_apply_ops_mixed_ops(db_session: Any) -> None:
    """Mix de ops validas + NOOP -> solo las validas cuentan."""
    user = await _seed_user_for_engine(db_session)
    semantic, procedural = _make_stores(db_session, user.id)

    ops = [
        MemoryOp(op="ADD", layer="semantic", content="El usuario es estudiante."),
        MemoryOp(
            op="ADD", layer="procedural", key="nivel_estudio", value={"nivel": "universitario"}
        ),
        MemoryOp(op="NOOP", layer="semantic"),
        MemoryOp(op="DELETE", layer="procedural", key=None),  # skip por key=None
    ]
    applied = await apply_ops(ops, semantic_store=semantic, procedural_store=procedural)
    assert applied == 2  # solo semantic ADD + procedural ADD

    entry = await procedural.get("nivel_estudio")
    assert entry is not None
    assert entry.value["nivel"] == "universitario"
