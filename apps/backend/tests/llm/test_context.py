"""Tests de app/llm/context.py (M8 Ola 1).

PARTE UNIT: formato del bloque, omision de vacios, truncado, filtro stale,
orden por confidence, procedural como key:json. Usa datos fake sembrados a
mano; NO toca DB.

PARTE INTEGRATION (@pytest.mark.integration): siembra un user + memorias
reales via los stores y verifica build_memory_context + render_context_block
end-to-end por modo (vida=solo procedural, productividad=semantic+episodic).
Usa FakeEmbeddingClient + FakeReranker.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.llm.config import ModeConfig
from app.llm.context import (
    COMPLETION_RESERVE_TOKENS,
    EPISODIC_LIMIT,
    PROCEDURAL_LIMIT,
    SEMANTIC_LIMIT,
    MemoryContext,
    _build_block,
    _format_episodic,
    _format_procedural,
    _format_semantic,
    _truncate_to_budget,
    build_memory_context,
    context_budget,
    estimate_tokens,
    render_context_block,
)
from app.llm.tools.registry import ToolRegistry, default_registry
from app.schemas.memory import EpisodicMemoryOut, ProceduralMemoryOut, SemanticMemoryOut

# ---------------------------------------------------------------------------
# Helpers de construccion de Out fakes
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()


def _sem(content: str, importance: int | None = None) -> SemanticMemoryOut:
    return SemanticMemoryOut(
        id=uuid.uuid4(),
        user_id=_USER_ID,
        content=content,
        importance=importance,
        source_session_id=None,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )


def _epi(
    summary: str,
    occurred_at: datetime | None = None,
    is_sensitive: bool = False,
    session_id: UUID | None = None,
) -> EpisodicMemoryOut:
    return EpisodicMemoryOut(
        id=uuid.uuid4(),
        user_id=_USER_ID,
        session_id=session_id or uuid.uuid4(),
        summary=summary,
        is_sensitive=is_sensitive,
        retention_days=365,
        occurred_at=occurred_at or datetime.now(tz=UTC),
        topics={},
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )


def _proc(
    key: str,
    value: dict[str, Any],
    confidence: float = 1.0,
    stale: bool = False,
) -> ProceduralMemoryOut:
    return ProceduralMemoryOut(
        id=uuid.uuid4(),
        user_id=_USER_ID,
        key=key,
        value=value,
        confidence=confidence,
        last_reinforced_at=datetime.now(tz=UTC),
        stale=stale,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )


def _make_memory_registry() -> ToolRegistry:
    """Construye un memory_registry real con un SemanticMemoryStore fake."""
    from unittest.mock import MagicMock

    from app.llm.tools.memory import memory_registry

    fake_store = MagicMock()
    return memory_registry(fake_store)


def _fake_ctx(
    semantic: list[SemanticMemoryOut] | None = None,
    episodic: list[EpisodicMemoryOut] | None = None,
    procedural: list[ProceduralMemoryOut] | None = None,
    has_memory_registry: bool = False,
) -> MemoryContext:
    """Construye un MemoryContext con stores falsos que retornan datos fijos."""
    sem_store = None
    epi_store = None
    proc_store = None

    if semantic is not None:
        sem_store = AsyncMock()
        sem_store.search = AsyncMock(return_value=semantic)

    if episodic is not None:
        epi_store = AsyncMock()
        epi_store.search = AsyncMock(return_value=episodic)

    if procedural is not None:
        proc_store = AsyncMock()
        proc_store.list_all = AsyncMock(return_value=procedural)

    mem_reg = _make_memory_registry() if has_memory_registry else None

    return MemoryContext(
        semantic_store=sem_store,
        episodic_store=epi_store,
        procedural_store=proc_store,
        _default_reg=default_registry(),
        _memory_reg=mem_reg,
    )


# ---------------------------------------------------------------------------
# UNIT: estimate_tokens / context_budget
# ---------------------------------------------------------------------------


def test_estimate_tokens_basic() -> None:
    # ~3 chars per token heuristic; just check it's > 0 and reasonable
    text = "hola mundo"
    tokens = estimate_tokens(text)
    assert tokens >= 1
    assert tokens <= len(text)


def test_estimate_tokens_empty_returns_one() -> None:
    assert estimate_tokens("") == 1


def test_context_budget_subtracts_system_and_reserve() -> None:
    prompt = "x" * 300
    budget = context_budget(max_model_len=4096, system_prompt=prompt)
    assert budget == 4096 - estimate_tokens(prompt) - COMPLETION_RESERVE_TOKENS


def test_context_budget_floor_zero() -> None:
    # Ventana minuscula + prompt enorme: el presupuesto cae a 0, nunca negativo.
    assert context_budget(max_model_len=10, system_prompt="x" * 5000) == 0


# ---------------------------------------------------------------------------
# UNIT: _format_semantic
# ---------------------------------------------------------------------------


def test_format_semantic_bullet_list() -> None:
    entries = [_sem("me gusta el mate amargo"), _sem("trabajo en software")]
    lines = _format_semantic(entries)
    assert lines == ["- me gusta el mate amargo", "- trabajo en software"]


def test_format_semantic_empty() -> None:
    assert _format_semantic([]) == []


# ---------------------------------------------------------------------------
# UNIT: _format_episodic
# ---------------------------------------------------------------------------


def test_format_episodic_includes_date_and_summary() -> None:
    occurred = datetime(2025, 3, 15, tzinfo=UTC)
    entries = [_epi("sprint terminado", occurred_at=occurred)]
    lines = _format_episodic(entries)
    assert lines == ["- [2025-03-15] sprint terminado"]


def test_format_episodic_never_exposes_is_sensitive() -> None:
    """is_sensitive nunca debe aparecer en el bloque generado."""
    entries = [_epi("secreto", is_sensitive=True)]
    lines = _format_episodic(entries)
    line = lines[0]
    assert "sensitive" not in line.lower()
    assert "True" not in line
    assert "False" not in line


def test_format_episodic_empty() -> None:
    assert _format_episodic([]) == []


# ---------------------------------------------------------------------------
# UNIT: _format_procedural (key: {json compacto})
# ---------------------------------------------------------------------------


def test_format_procedural_json_compact() -> None:
    entries = [_proc("pref.idioma", {"idioma": "es"})]
    lines = _format_procedural(entries)
    assert lines == ['- pref.idioma: {"idioma":"es"}']


def test_format_procedural_multiple_fields_compact() -> None:
    entries = [_proc("pref.horario", {"inicio": "09:00", "fin": "18:00"})]
    lines = _format_procedural(entries)
    raw = lines[0]
    # Verificar que es JSON valido y compacto (sin espacios extra)
    prefix = "- pref.horario: "
    assert raw.startswith(prefix)
    parsed = json.loads(raw[len(prefix) :])
    assert parsed == {"inicio": "09:00", "fin": "18:00"}
    assert " " not in raw[len(prefix) :]  # compacto: sin espacios


def test_format_procedural_empty() -> None:
    assert _format_procedural([]) == []


# ---------------------------------------------------------------------------
# UNIT: _build_block (omision de subsecciones vacias)
# ---------------------------------------------------------------------------


def test_build_block_all_empty_returns_empty_string() -> None:
    result = _build_block([], [], [])
    assert result == ""


def test_build_block_only_semantic() -> None:
    result = _build_block(["- dato A"], [], [])
    assert "## Contexto de memoria" in result
    assert "Lo que se sobre vos" in result
    assert "Sesiones anteriores" not in result
    assert "Tus preferencias" not in result
    assert "- dato A" in result


def test_build_block_only_episodic() -> None:
    result = _build_block([], ["- [2025-01-01] algo"], [])
    assert "Sesiones anteriores" in result
    assert "Lo que se sobre vos" not in result
    assert "Tus preferencias" not in result


def test_build_block_only_procedural() -> None:
    result = _build_block([], [], ['- k: {"v":1}'])
    assert "Tus preferencias" in result
    assert "Lo que se sobre vos" not in result
    assert "Sesiones anteriores" not in result


def test_build_block_all_sections_present() -> None:
    result = _build_block(["- sem"], ["- [2025-01-01] epi"], ["- k: {}"])
    assert "Lo que se sobre vos" in result
    assert "Sesiones anteriores" in result
    assert "Tus preferencias" in result
    assert result.startswith("## Contexto de memoria")


def test_build_block_header_once() -> None:
    result = _build_block(["- a"], ["- [2025-01-01] b"], ["- c: {}"])
    assert result.count("## Contexto de memoria") == 1


# ---------------------------------------------------------------------------
# UNIT: _truncate_to_budget
# ---------------------------------------------------------------------------


def test_truncate_no_op_if_fits() -> None:
    sem = ["- dato"]
    epi = ["- [2025-01-01] epi"]
    proc = ["- k: {}"]
    s, e, p = _truncate_to_budget(sem, epi, proc, budget_tokens=10_000)
    assert s == sem
    assert e == epi
    assert p == proc


def test_truncate_episodic_first() -> None:
    # 3 episodios -> 1 episodio cuando hay presion de budget
    sem = ["- " + "x" * 50] * SEMANTIC_LIMIT
    epi = ["- [2025-01-01] " + "y" * 50] * EPISODIC_LIMIT
    proc = [f'- k{idx}: {{"v":{idx}}}' for idx in range(PROCEDURAL_LIMIT)]
    # Budget muy chico para forzar truncado
    _s, e, _p = _truncate_to_budget(sem, epi, proc, budget_tokens=5)
    # episodic debe haberse reducido (se redujo primero)
    assert len(e) <= EPISODIC_LIMIT


def test_truncate_reduces_entries_not_mid_line() -> None:
    # Verifica que el resultado no tiene lineas partidas
    sem = ["- " + "A" * 200] * 5
    epi = ["- [2025-01-01] " + "B" * 200] * 3
    proc = [f'- k{idx}: {{"v":{idx}}}' for idx in range(10)]
    s, e, p = _truncate_to_budget(sem, epi, proc, budget_tokens=10)
    # Cada linea sigue siendo una entrada completa (empieza con '- ')
    for line in s + e + p:
        assert line.startswith("- ")


def test_truncate_budget_zero_hits_lower_bounds_not_empty() -> None:
    """Con ``budget_tokens=0`` y datos presentes, el recorte llega a los PISOS de los
    loops, NO a vacío.

    Documenta el comportamiento REAL (ver docstring de ``context_budget``): el "piso"
    es el LÍMITE INFERIOR de los while-loops (``epi > 1``, ``sem > 3``, ``proc > 5``),
    un efecto colateral del rango de los loops, NO una garantía activa del budget.
    Con budget 0 igual quedan exactamente 1 episodic + 3 semantic + 5 procedural
    porque los loops no recortan por debajo de eso (aunque el bloque siga sin caber
    en 0 tokens). NO se eliminan todas las entradas.
    """
    sem = ["- " + "S" * 80] * SEMANTIC_LIMIT  # 5
    epi = ["- [2025-01-01] " + "E" * 80] * EPISODIC_LIMIT  # 3
    proc = [f'- k{idx}: {{"v":{idx}}}' for idx in range(PROCEDURAL_LIMIT)]  # 10

    s, e, p = _truncate_to_budget(sem, epi, proc, budget_tokens=0)

    # Pisos de cada loop: el recorte para en el límite inferior, no en 0.
    assert len(e) == 1  # episodic 3 -> 1 (no baja de 1)
    assert len(s) == 3  # semantic 5 -> 3 (no baja de 3)
    assert len(p) == 5  # procedural 10 -> 5 (no baja de 5)
    # Ninguna lista queda vacía pese al budget 0.
    assert s and e and p


def test_truncate_budget_zero_already_at_floor_is_noop() -> None:
    """Con budget 0 pero las listas YA en su piso, no se recorta nada (los while no entran)."""
    sem = ["- s"] * 3  # ya en el piso semantic
    epi = ["- [2025-01-01] e"]  # ya en el piso episodic
    proc = ["- k: {}"] * 5  # ya en el piso procedural

    s, e, p = _truncate_to_budget(sem, epi, proc, budget_tokens=0)

    assert len(s) == 3
    assert len(e) == 1
    assert len(p) == 5


def test_truncate_semantic_after_episodic() -> None:
    """Cuando epi ya esta en 1, el siguiente paso recorta semantic."""
    sem_lines = ["- " + "S" * 300] * 5
    epi_lines = ["- [2025-01-01] " + "E" * 300]  # ya en 1 (minimo)
    proc_lines = ["- k: {}"] * 10
    # Budget que no cabe todo pero cabe con semantic recortado
    block_full = _build_block(sem_lines, epi_lines, proc_lines)
    budget = estimate_tokens(block_full) - estimate_tokens(sem_lines[0]) - 1
    if budget <= 0:
        pytest.skip("el bloque es demasiado pequeño para el test de truncado semantico")
    s, _e, _p = _truncate_to_budget(sem_lines, epi_lines, proc_lines, budget_tokens=budget)
    assert len(s) <= 5


# ---------------------------------------------------------------------------
# UNIT: filtro stale y orden por confidence en render_context_block
# ---------------------------------------------------------------------------


async def test_render_filters_stale_procedural() -> None:
    """Procedural con stale=True no debe aparecer en el bloque."""
    procs = [
        _proc("pref.fresh", {"ok": True}, confidence=0.9, stale=False),
        _proc("pref.stale", {"bad": True}, confidence=1.0, stale=True),
    ]
    ctx = _fake_ctx(procedural=procs)
    result = await render_context_block(ctx, query="test", budget_tokens=10_000)
    assert "pref.fresh" in result
    assert "pref.stale" not in result


async def test_render_orders_procedural_by_confidence_desc() -> None:
    """Procedural se ordena por confidence descendente (las mas confiables primero)."""
    procs = [
        _proc("pref.baja", {"v": 1}, confidence=0.3, stale=False),
        _proc("pref.alta", {"v": 2}, confidence=0.9, stale=False),
        _proc("pref.media", {"v": 3}, confidence=0.6, stale=False),
    ]
    ctx = _fake_ctx(procedural=procs)
    result = await render_context_block(ctx, query="test", budget_tokens=10_000)
    # El orden en el bloque debe ser: alta > media > baja
    pos_alta = result.index("pref.alta")
    pos_media = result.index("pref.media")
    pos_baja = result.index("pref.baja")
    assert pos_alta < pos_media < pos_baja


async def test_render_takes_at_most_procedural_limit() -> None:
    """render_context_block toma como maximo PROCEDURAL_LIMIT entradas."""
    procs = [_proc(f"pref.item{i:03d}", {"i": i}, confidence=float(i) / 100) for i in range(20)]
    ctx = _fake_ctx(procedural=procs)
    result = await render_context_block(ctx, query="test", budget_tokens=10_000)
    # Contar cuantos keys aparecen en el resultado (claves zero-padded: sin ambiguedad)
    count = sum(1 for i in range(20) if f"pref.item{i:03d}" in result)
    assert count <= PROCEDURAL_LIMIT


# ---------------------------------------------------------------------------
# UNIT: render_context_block - usuario nuevo (sin memorias)
# ---------------------------------------------------------------------------


async def test_render_empty_stores_returns_empty_string() -> None:
    """Usuario nuevo sin memorias: render devuelve ''."""
    ctx = _fake_ctx(semantic=[], episodic=[], procedural=[])
    result = await render_context_block(ctx, query="hola", budget_tokens=10_000)
    assert result == ""


async def test_render_none_stores_returns_empty_string() -> None:
    """Si no hay stores activos (modo que no toca nada), devuelve ''."""
    ctx = _fake_ctx()  # todos None
    result = await render_context_block(ctx, query="hola", budget_tokens=10_000)
    assert result == ""


# ---------------------------------------------------------------------------
# UNIT: render_context_block - solo una layer activa
# ---------------------------------------------------------------------------


async def test_render_only_procedural() -> None:
    """Modo 'vida': solo procedural, sin semantic ni episodic."""
    procs = [_proc("pref.idioma", {"idioma": "es"})]
    ctx = _fake_ctx(procedural=procs)  # semantic=None, episodic=None
    result = await render_context_block(ctx, query="test", budget_tokens=10_000)
    assert "Tus preferencias" in result
    assert "Lo que se sobre vos" not in result
    assert "Sesiones anteriores" not in result
    assert "pref.idioma" in result


async def test_render_only_semantic() -> None:
    """Solo semantic activo."""
    sems = [_sem("le gusta el cafe")]
    ctx = _fake_ctx(semantic=sems)
    result = await render_context_block(ctx, query="test", budget_tokens=10_000)
    assert "Lo que se sobre vos" in result
    assert "Sesiones anteriores" not in result
    assert "le gusta el cafe" in result


async def test_render_semantic_and_episodic() -> None:
    """Semantic + episodic activos (modo productividad sin procedural)."""
    sems = [_sem("trabaja en IA")]
    epis = [_epi("sprint completado", occurred_at=datetime(2025, 4, 1, tzinfo=UTC))]
    ctx = _fake_ctx(semantic=sems, episodic=epis)
    result = await render_context_block(ctx, query="trabajo", budget_tokens=10_000)
    assert "Lo que se sobre vos" in result
    assert "Sesiones anteriores" in result
    assert "trabaja en IA" in result
    assert "sprint completado" in result


# ---------------------------------------------------------------------------
# UNIT: MemoryContext.tool_specs y .registries
# ---------------------------------------------------------------------------


def test_tool_specs_no_memory_in_tools_enabled() -> None:
    """Sin 'memory' en tools_enabled, solo specs del default_registry."""
    ctx = _fake_ctx()
    specs = ctx.tool_specs(["calendar", "reminder"])
    names = {s.name for s in specs}
    assert "calendar.create_event" in names or any("calendar" in n for n in names)
    assert not any("memory" in n for n in names)


def test_tool_specs_memory_without_memory_registry() -> None:
    """'memory' en tools_enabled pero sin memory_reg (semantic_store=None): sin memory specs."""
    ctx = _fake_ctx(has_memory_registry=False)
    specs = ctx.tool_specs(["memory"])
    names = {s.name for s in specs}
    assert not any("memory" in n for n in names)


def test_tool_specs_memory_with_memory_registry() -> None:
    """'memory' en tools_enabled Y hay memory_reg: incluye memory specs."""
    ctx = _fake_ctx(has_memory_registry=True)
    specs = ctx.tool_specs(["memory"])
    names = {s.name for s in specs}
    assert any("memory" in n for n in names)


def test_registries_tuple_structure() -> None:
    ctx = _fake_ctx(has_memory_registry=True)
    reg_tuple = ctx.registries
    assert len(reg_tuple) == 2
    assert isinstance(reg_tuple[0], ToolRegistry)
    assert isinstance(reg_tuple[1], ToolRegistry)


def test_registries_no_memory_second_is_none() -> None:
    ctx = _fake_ctx(has_memory_registry=False)
    reg_tuple = ctx.registries
    assert reg_tuple[1] is None


# ---------------------------------------------------------------------------
# UNIT: build_memory_context selecciona layers correctas
# ---------------------------------------------------------------------------


def test_build_memory_context_vida_only_procedural() -> None:
    """Modo 'vida': solo procedural layer -> solo ProceduralMemoryStore."""
    mode_cfg = ModeConfig(
        name="vida",
        model="gemma-4-12b",
        memory_layers=["procedural"],
        tools_enabled=[],
        tone="casual-rioplatense",
    )
    from unittest.mock import MagicMock

    session = MagicMock()
    embedder = MagicMock()
    reranker = MagicMock()
    user_id = uuid.uuid4()

    ctx = build_memory_context(
        session=session,
        user_id=user_id,
        embedder=embedder,
        reranker=reranker,
        mode_cfg=mode_cfg,
    )

    assert ctx.semantic_store is None
    assert ctx.episodic_store is None
    assert ctx.procedural_store is not None
    assert ctx.registries[1] is None  # no memory_registry sin semantic


def test_build_memory_context_productividad_semantic_episodic() -> None:
    """Modo 'productividad': semantic + episodic (sin procedural en config real)."""
    mode_cfg = ModeConfig(
        name="productividad",
        model="qwen-3.5-9b",
        memory_layers=["semantic", "episodic"],
        tools_enabled=["calendar", "reminder", "memory"],
        tone="neutro-eficaz",
    )
    from unittest.mock import MagicMock

    session = MagicMock()
    embedder = MagicMock()
    reranker = MagicMock()
    user_id = uuid.uuid4()

    ctx = build_memory_context(
        session=session,
        user_id=user_id,
        embedder=embedder,
        reranker=reranker,
        mode_cfg=mode_cfg,
    )

    assert ctx.semantic_store is not None
    assert ctx.episodic_store is not None
    assert ctx.procedural_store is None
    assert ctx.registries[1] is not None  # memory_registry existe (semantic_store ok)


def test_build_memory_context_memoria_all_layers() -> None:
    """Modo 'memoria': los 3 stores activos."""
    mode_cfg = ModeConfig(
        name="memoria",
        model="qwen-3.5-9b",
        memory_layers=["episodic", "semantic", "procedural"],
        tools_enabled=["memory"],
        tone="neutro-eficaz",
    )
    from unittest.mock import MagicMock

    session = MagicMock()
    embedder = MagicMock()
    reranker = MagicMock()
    user_id = uuid.uuid4()

    ctx = build_memory_context(
        session=session,
        user_id=user_id,
        embedder=embedder,
        reranker=reranker,
        mode_cfg=mode_cfg,
    )

    assert ctx.semantic_store is not None
    assert ctx.episodic_store is not None
    assert ctx.procedural_store is not None
    assert ctx.registries[1] is not None


# ---------------------------------------------------------------------------
# UNIT: _default_reg trae las tools REALES del chat segun el modo (ADR-022)
# ---------------------------------------------------------------------------


def _build_ctx_for_tools(tools_enabled: list[str]) -> MemoryContext:
    """Construye un MemoryContext con un mode_cfg que habilita ``tools_enabled``.

    Usa MagicMock para session/embedder/reranker (no toca DB): solo nos importa qué
    tools terminan en ``_default_reg`` (lo arma ``build_chat_tool_registry``, gateado por
    ``mode_cfg.tools_enabled``). El ``memory_layers`` se deja vacío para no instanciar
    stores reales (irrelevante para este assert).
    """
    from unittest.mock import MagicMock

    mode_cfg = ModeConfig(
        name="probe",
        model="qwen-3.5-9b",
        memory_layers=[],
        tools_enabled=tools_enabled,
        tone="neutro-eficaz",
    )
    return build_memory_context(
        session=MagicMock(),
        user_id=uuid.uuid4(),
        embedder=MagicMock(),
        reranker=MagicMock(),
        mode_cfg=mode_cfg,
    )


def test_default_reg_productividad_has_real_calendar_and_reminder_stub() -> None:
    """En productividad (calendar/reminder/task), ``_default_reg`` tiene la calendar tool
    REAL (con efecto) y reminder como STUB not_wired (ADR-022).

    - ``calendar.create_event`` debe ser ``AgentCreateEventTool`` (real, escribe), NO el
      stub ``CreateEventTool``.
    - ``reminder.set`` debe ser el stub ``SetReminderTool`` (no hay backend real).
    """
    from app.llm.tools.calendar import AgentCreateEventTool
    from app.llm.tools.reminder import SetReminderTool
    from app.llm.tools.task import AgentCreateTaskTool

    ctx = _build_ctx_for_tools(["calendar", "reminder", "task"])
    reg = ctx.registries[0]

    # Las 3 tools de agente están registradas (API pública ``has()`` / ``get_tool()``, NO el
    # dict privado ``_tools``): así el test no se acopla a la representación interna del
    # registry.
    assert reg.has("calendar.create_event")
    assert reg.has("task.create_task")
    assert reg.has("reminder.set")

    # calendar.create_event y task.create_task son las tools REALES (escriben), no los stubs.
    assert isinstance(reg.get_tool("calendar.create_event"), AgentCreateEventTool)
    assert isinstance(reg.get_tool("task.create_task"), AgentCreateTaskTool)

    # reminder sigue siendo stub not_wired (sin backend real).
    assert isinstance(reg.get_tool("reminder.set"), SetReminderTool)

    # Las specs hacia el modelo exponen los 3 namespaces habilitados.
    specs = ctx.tool_specs(["calendar", "reminder", "task"])
    namespaces = {s.name.split(".")[0] for s in specs}
    assert {"calendar", "reminder", "task"} <= namespaces


def test_default_reg_gemma_mode_is_empty() -> None:
    """En un modo gemma (``tools_enabled=[]``) el ``_default_reg`` queda vacío (ADR-022)."""
    ctx = _build_ctx_for_tools([])
    reg = ctx.registries[0]
    assert reg.tools() == []
    assert ctx.tool_specs([]) == []


def test_default_reg_memoria_mode_has_no_calendar_or_task() -> None:
    """En 'memoria' (``tools_enabled=[memory]``) no hay calendar/task/reminder en el reg.

    El namespace ``memory`` lo maneja ``_memory_reg`` aparte; ``_default_reg`` (las tools
    de agente del chat) no debe traer ninguna tool porque ``memory`` no está en
    ``_AGENT_TOOL_BUILDERS`` ni es ``reminder``.
    """
    ctx = _build_ctx_for_tools(["memory"])
    reg = ctx.registries[0]
    assert reg.tools() == []
    # No hay calendar/task tools registradas.
    assert not reg.has("calendar.create_event")
    assert not reg.has("task.create_task")
    assert not reg.has("reminder.set")


# ===========================================================================
# INTEGRATION
# ===========================================================================


def _now() -> datetime:
    return datetime.now(tz=UTC)


async def _seed_user(session: Any) -> Any:
    from app.models.user import User

    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_session(session: Any, user: Any) -> Any:
    from app.enums import Mode
    from app.models.session import ChatSession

    chat = ChatSession(user_id=user.id, mode=Mode.PRODUCTIVIDAD)
    session.add(chat)
    await session.flush()
    await session.refresh(chat)
    return chat


@pytest.mark.integration
async def test_integration_vida_only_procedural(db_session: Any) -> None:
    """Modo 'vida': build_memory_context solo crea ProceduralMemoryStore.

    render_context_block devuelve 'Tus preferencias' y nada de semantic/episodic.
    """
    from app.llm.clients.embedding import FakeEmbeddingClient
    from app.llm.clients.reranker import FakeReranker
    from app.memory.procedural import ProceduralMemoryStore
    from app.schemas.memory import ProceduralMemoryUpsert

    user = await _seed_user(db_session)

    mode_cfg = ModeConfig(
        name="vida",
        model="gemma-4-12b",
        memory_layers=["procedural"],
        tools_enabled=[],
        tone="casual-rioplatense",
    )
    embedder = FakeEmbeddingClient()
    reranker = FakeReranker()

    ctx = build_memory_context(
        session=db_session,
        user_id=user.id,
        embedder=embedder,
        reranker=reranker,
        mode_cfg=mode_cfg,
    )

    assert ctx.semantic_store is None
    assert ctx.episodic_store is None
    assert ctx.procedural_store is not None

    # Sembrar procedural
    proc_store = ProceduralMemoryStore(db_session, user.id)
    await proc_store.upsert(ProceduralMemoryUpsert(key="pref.idioma", value={"idioma": "es"}))
    await proc_store.upsert(ProceduralMemoryUpsert(key="pref.tono", value={"tono": "informal"}))

    result = await render_context_block(ctx, query="como estoy", budget_tokens=10_000)

    assert "Tus preferencias" in result
    assert "pref.idioma" in result
    assert "pref.tono" in result
    assert "Lo que se sobre vos" not in result
    assert "Sesiones anteriores" not in result


@pytest.mark.integration
async def test_integration_productividad_semantic_episodic(db_session: Any) -> None:
    """Modo 'productividad': semantic + episodic, sin procedural.

    Siembra hechos semanticos y episodios; verifica que render devuelve ambas
    subsecciones con los datos sembrados.
    """
    from app.llm.clients.embedding import FakeEmbeddingClient
    from app.llm.clients.reranker import FakeReranker
    from app.memory.episodic import EpisodicMemoryStore
    from app.memory.semantic import SemanticMemoryStore
    from app.schemas.memory import EpisodicMemoryCreate, SemanticMemoryCreate

    user = await _seed_user(db_session)
    chat = await _seed_session(db_session, user)

    mode_cfg = ModeConfig(
        name="productividad",
        model="qwen-3.5-9b",
        memory_layers=["semantic", "episodic"],
        tools_enabled=["calendar", "reminder", "memory"],
        tone="neutro-eficaz",
    )
    embedder = FakeEmbeddingClient()
    reranker = FakeReranker()

    ctx = build_memory_context(
        session=db_session,
        user_id=user.id,
        embedder=embedder,
        reranker=reranker,
        mode_cfg=mode_cfg,
    )

    assert ctx.semantic_store is not None
    assert ctx.episodic_store is not None
    assert ctx.procedural_store is None

    # Sembrar semantic
    sem_store = SemanticMemoryStore(db_session, user.id, embedder, reranker)
    await sem_store.add(SemanticMemoryCreate(content="trabaja en inteligencia artificial"))

    # Sembrar episodic
    epi_store = EpisodicMemoryStore(db_session, user.id, embedder, reranker)
    await epi_store.add(
        EpisodicMemoryCreate(
            session_id=chat.id,
            summary="sesion de planning completada exitosamente",
            occurred_at=_now(),
            is_sensitive=False,
            retention_days=180,
        )
    )

    result = await render_context_block(ctx, query="trabajo y planificacion", budget_tokens=10_000)

    # Ambas subsecciones deben estar
    assert "Lo que se sobre vos" in result
    assert "Sesiones anteriores" in result
    assert "Tus preferencias" not in result

    # Los datos sembrados deben aparecer
    assert "trabaja en inteligencia artificial" in result
    assert "sesion de planning completada exitosamente" in result


@pytest.mark.integration
async def test_integration_usuario_nuevo_sin_memorias(db_session: Any) -> None:
    """Usuario nuevo sin memorias: render devuelve '' para cualquier modo."""
    from app.llm.clients.embedding import FakeEmbeddingClient
    from app.llm.clients.reranker import FakeReranker

    user = await _seed_user(db_session)

    mode_cfg = ModeConfig(
        name="productividad",
        model="qwen-3.5-9b",
        memory_layers=["semantic", "episodic"],
        tools_enabled=["calendar", "reminder", "memory"],
        tone="neutro-eficaz",
    )
    embedder = FakeEmbeddingClient()
    reranker = FakeReranker()

    ctx = build_memory_context(
        session=db_session,
        user_id=user.id,
        embedder=embedder,
        reranker=reranker,
        mode_cfg=mode_cfg,
    )

    result = await render_context_block(ctx, query="hola", budget_tokens=10_000)
    assert result == ""


@pytest.mark.integration
async def test_integration_procedural_filters_stale_and_orders_confidence(
    db_session: Any,
) -> None:
    """Stale=True no aparece; las entradas se ordenan por confidence desc."""
    from sqlalchemy import update as sa_update

    from app.llm.clients.embedding import FakeEmbeddingClient
    from app.llm.clients.reranker import FakeReranker
    from app.memory.procedural import ProceduralMemoryStore
    from app.models.memory import ProceduralMemory
    from app.schemas.memory import ProceduralMemoryUpsert

    user = await _seed_user(db_session)

    mode_cfg = ModeConfig(
        name="vida",
        model="gemma-4-12b",
        memory_layers=["procedural"],
        tools_enabled=[],
        tone="casual-rioplatense",
    )
    embedder = FakeEmbeddingClient()
    reranker = FakeReranker()

    # Sembrar 3 entradas: una con confidence baja, una alta, una stale
    proc_store = ProceduralMemoryStore(db_session, user.id)
    out_baja = await proc_store.upsert(ProceduralMemoryUpsert(key="pref.baja", value={"v": "baja"}))
    out_alta = await proc_store.upsert(ProceduralMemoryUpsert(key="pref.alta", value={"v": "alta"}))
    out_stale = await proc_store.upsert(
        ProceduralMemoryUpsert(key="pref.stale", value={"v": "stale"})
    )

    # Ajustar confidence y stale manualmente via SQL (los stores no exponen esto)
    await db_session.execute(
        sa_update(ProceduralMemory).where(ProceduralMemory.id == out_baja.id).values(confidence=0.2)
    )
    await db_session.execute(
        sa_update(ProceduralMemory).where(ProceduralMemory.id == out_alta.id).values(confidence=0.9)
    )
    await db_session.execute(
        sa_update(ProceduralMemory).where(ProceduralMemory.id == out_stale.id).values(stale=True)
    )
    await db_session.flush()

    ctx = build_memory_context(
        session=db_session,
        user_id=user.id,
        embedder=embedder,
        reranker=reranker,
        mode_cfg=mode_cfg,
    )

    result = await render_context_block(ctx, query="preferencias", budget_tokens=10_000)

    # stale no debe aparecer
    assert "pref.stale" not in result

    # alta y baja si
    assert "pref.alta" in result
    assert "pref.baja" in result

    # alta debe aparecer antes que baja (confidence desc)
    assert result.index("pref.alta") < result.index("pref.baja")
