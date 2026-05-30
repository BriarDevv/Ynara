"""Modulo de inyeccion de contexto de memoria para el router LLM (M8 Ola 1).

``build_memory_context`` instancia SOLO los stores cuyas layers estan en
``mode_cfg.memory_layers`` (vida=solo procedural, nunca toca semantic/episodic).
``render_context_block`` recupera los datos por layer, los formatea en Markdown
y aplica un presupuesto de tokens para no inflar el context window.

Restricciones de diseno:
- ``is_sensitive`` de EpisodicMemoryOut NUNCA se expone al modelo (ADR-007).
- El filtrado/orden de procedural ocurre aqui, no en el store (list_all devuelve
  todo, el router filtra stale=False y ordena por confidence desc).
- El budget_tokens es una heuristica (len // 3): no se usa tiktoken para
  evitar dependencias pesadas en el path de respuesta.
- La truncacion elimina ENTRADAS COMPLETAS en el orden episodic(3->1) ->
  semantic(5->3) -> procedural(10->5). Nunca a mitad de linea.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.llm.config import ModeConfig
from app.llm.schemas import ToolSpec
from app.llm.tools.memory import memory_registry
from app.llm.tools.registry import ToolRegistry, default_registry
from app.memory.episodic import EpisodicMemoryStore
from app.memory.procedural import ProceduralMemoryStore
from app.memory.semantic import SemanticMemoryStore
from app.schemas.memory import EpisodicMemoryOut, ProceduralMemoryOut, SemanticMemoryOut

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

SEMANTIC_LIMIT: int = 5
EPISODIC_LIMIT: int = 3
PROCEDURAL_LIMIT: int = 10

# Tokens reservados para la completion del modelo (no disponibles para contexto).
COMPLETION_RESERVE_TOKENS: int = 512


# ---------------------------------------------------------------------------
# Helpers de estimacion de tokens
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Estimacion rapida de tokens a partir de caracteres.

    Heuristica: ~3 caracteres por token (conservadora para texto en espanol).
    Sin dependencias de tiktoken ni sentencepiece.
    """
    return max(1, len(text) // 3)


def _budget_tokens(context_window: int) -> int:
    """Tokens disponibles para inyectar contexto de memoria.

    Descuenta el COMPLETION_RESERVE_TOKENS y deja un margen conservador para
    el system prompt y el mensaje del usuario. En M8 el prompt base ocupa
    ~200-400 tokens segun el modo; dejamos el contexto competir con ese rango.

    Returns:
        Presupuesto en tokens para el bloque de contexto de memoria.
    """
    return max(0, context_window - COMPLETION_RESERVE_TOKENS)


# ---------------------------------------------------------------------------
# MemoryContext: dataclass frozen que encapsula stores + registries
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemoryContext:
    """Contexto de memoria construido por ``build_memory_context``.

    Solo contiene los stores activos para el modo. Los stores que no estan en
    ``memory_layers`` del modo NO se instancian (evita queries innecesarias).

    Atributos:
        semantic_store: Store semantico, o None si 'semantic' no esta en layers.
        episodic_store: Store episodico, o None si 'episodic' no esta en layers.
        procedural_store: Store procedural, o None si 'procedural' no esta en layers.
        _default_reg: Registry con calendar + reminder (siempre presente).
        _memory_reg: Registry con memory tools, o None si no procede.
    """

    semantic_store: SemanticMemoryStore | None
    episodic_store: EpisodicMemoryStore | None
    procedural_store: ProceduralMemoryStore | None
    _default_reg: ToolRegistry = field(repr=False)
    _memory_reg: ToolRegistry | None = field(repr=False)

    def tool_specs(self, tools_enabled: list[str]) -> list[ToolSpec]:
        """ToolSpec para el modelo, segun los namespaces habilitados.

        Combina default_registry + memory_registry si 'memory' esta en
        tools_enabled Y existe un semantic_store (decision de diseno: si
        memory esta en tools_enabled pero no hay semantic_store, no tiene
        sentido exponer memory.search al modelo).

        Args:
            tools_enabled: Lista de namespaces habilitados para el modo activo.

        Returns:
            Lista de ToolSpec lista para pasarle al LLMClient.
        """
        specs = list(self._default_reg.specs_for(tools_enabled))
        if "memory" in tools_enabled and self._memory_reg is not None:
            specs.extend(self._memory_reg.specs_for(["memory"]))
        return specs

    @property
    def registries(self) -> tuple[ToolRegistry, ToolRegistry | None]:
        """Tupla (default_registry, memory_registry|None) para el tool loop.

        El router usa esto para ejecutar tool calls por nombre: llama
        execute() en el default primero, luego en el memory si existe.
        """
        return (self._default_reg, self._memory_reg)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_memory_context(
    *,
    session: AsyncSession,
    user_id: UUID,
    embedder: EmbeddingClient,
    reranker: Reranker,
    mode_cfg: ModeConfig,
) -> MemoryContext:
    """Instancia los stores y registries necesarios para el modo activo.

    Solo construye los stores cuyas layers estan en mode_cfg.memory_layers:
    - vida (solo 'procedural') -> solo ProceduralMemoryStore, sin semantic/episodic.
    - estudio ('episodic', 'procedural') -> Episodic + Procedural, sin Semantic.
    - productividad ('semantic', 'episodic') -> Semantic + Episodic, sin Procedural.
    - memoria ('episodic', 'semantic', 'procedural') -> los 3 stores.

    El memory_registry se construye SOLO si hay un semantic_store (las 4 memory
    tools se ligan al SemanticMemoryStore; sin el, no tiene sentido construirlo).

    Args:
        session: AsyncSession de la request actual.
        user_id: UUID del usuario (liga la key de cifrado en los stores).
        embedder: Cliente de embeddings para semantic/episodic.
        reranker: Cliente de reranking para semantic/episodic.
        mode_cfg: Config del modo activo (determina que layers y tools estan activos).

    Returns:
        MemoryContext frozen con los stores y registries listos.
    """
    layers = set(mode_cfg.memory_layers)

    semantic_store: SemanticMemoryStore | None = None
    episodic_store: EpisodicMemoryStore | None = None
    procedural_store: ProceduralMemoryStore | None = None

    if "semantic" in layers:
        semantic_store = SemanticMemoryStore(session, user_id, embedder, reranker)
    if "episodic" in layers:
        episodic_store = EpisodicMemoryStore(session, user_id, embedder, reranker)
    if "procedural" in layers:
        procedural_store = ProceduralMemoryStore(session, user_id)

    mem_reg: ToolRegistry | None = None
    if semantic_store is not None:
        mem_reg = memory_registry(semantic_store)

    return MemoryContext(
        semantic_store=semantic_store,
        episodic_store=episodic_store,
        procedural_store=procedural_store,
        _default_reg=default_registry(),
        _memory_reg=mem_reg,
    )


# ---------------------------------------------------------------------------
# Formateo de entradas
# ---------------------------------------------------------------------------


def _format_semantic(entries: list[SemanticMemoryOut]) -> list[str]:
    """Formatea los hechos semanticos como lineas Markdown."""
    return [f"- {e.content}" for e in entries]


def _format_episodic(entries: list[EpisodicMemoryOut]) -> list[str]:
    """Formatea los episodios pasados como lineas Markdown.

    NUNCA incluye is_sensitive (ADR-007: no exponer al modelo).
    """
    lines: list[str] = []
    for e in entries:
        date_str = e.occurred_at.strftime("%Y-%m-%d")
        lines.append(f"- [{date_str}] {e.summary}")
    return lines


def _format_procedural(entries: list[ProceduralMemoryOut]) -> list[str]:
    """Formatea las preferencias procedurales como 'key: {json compacto}'."""
    return [
        f"- {e.key}: {json.dumps(e.value, ensure_ascii=False, separators=(',', ':'))}"
        for e in entries
    ]


def _build_block(
    semantic_lines: list[str],
    episodic_lines: list[str],
    procedural_lines: list[str],
) -> str:
    """Arma el bloque Markdown final. Omite subsecciones vacias.

    Returns:
        El bloque de contexto como string Markdown, o '' si todo esta vacio.
    """
    sections: list[str] = []

    if semantic_lines:
        sections.append("### Lo que se sobre vos\n" + "\n".join(semantic_lines))
    if episodic_lines:
        sections.append("### Sesiones anteriores\n" + "\n".join(episodic_lines))
    if procedural_lines:
        sections.append("### Tus preferencias\n" + "\n".join(procedural_lines))

    if not sections:
        return ""

    return "## Contexto de memoria\n\n" + "\n\n".join(sections)


def _truncate_to_budget(
    semantic_lines: list[str],
    episodic_lines: list[str],
    procedural_lines: list[str],
    budget_tokens: int,
) -> tuple[list[str], list[str], list[str]]:
    """Recorta entradas completas hasta que el bloque cabe en budget_tokens.

    Orden de recorte: episodic (3->1) -> semantic (5->3) -> procedural (10->5).
    Nunca recorta a mitad de linea: siempre elimina entradas completas.

    Args:
        semantic_lines: Lineas de hechos semanticos.
        episodic_lines: Lineas de episodios.
        procedural_lines: Lineas de preferencias.
        budget_tokens: Presupuesto maximo en tokens.

    Returns:
        Tupla (semantic_lines, episodic_lines, procedural_lines) recortadas.
    """
    sem = list(semantic_lines)
    epi = list(episodic_lines)
    proc = list(procedural_lines)

    def _fits() -> bool:
        block = _build_block(sem, epi, proc)
        return _estimate_tokens(block) <= budget_tokens

    if _fits():
        return sem, epi, proc

    # Paso 1: episodic 3 -> 1
    while len(epi) > 1:
        epi.pop()
        if _fits():
            return sem, epi, proc

    # Paso 2: semantic 5 -> 3
    while len(sem) > 3:
        sem.pop()
        if _fits():
            return sem, epi, proc

    # Paso 3: procedural 10 -> 5
    while len(proc) > 5:
        proc.pop()
        if _fits():
            return sem, epi, proc

    # Si aun no cabe, devolvemos lo que tenemos (el caller puede truncar mas
    # si lo necesita, pero no eliminamos todas las entradas aqui).
    return sem, epi, proc


# ---------------------------------------------------------------------------
# render_context_block
# ---------------------------------------------------------------------------


async def render_context_block(
    ctx: MemoryContext,
    *,
    query: str,
    budget_tokens: int,
) -> str:
    """Recupera y formatea el bloque de contexto de memoria para inyectar al LLM.

    Por layer:
    - semantic: search(query, limit=SEMANTIC_LIMIT)
    - episodic: search(query, limit=EPISODIC_LIMIT)
    - procedural: list_all() filtrado stale=False, ordenado por confidence desc,
      tomar los primeros PROCEDURAL_LIMIT (las preferencias mas confiables primero).

    El bloque resultante se trunca a budget_tokens eliminando entradas completas
    en el orden episodic -> semantic -> procedural.

    Subsecciones vacias se omiten. Si no hay nada, devuelve ''.
    NUNCA expone EpisodicMemoryOut.is_sensitive al modelo.

    Args:
        ctx: MemoryContext con los stores activos para el modo.
        query: Texto de la request del usuario (para las busquedas ANN).
        budget_tokens: Presupuesto de tokens para el bloque de contexto.

    Returns:
        Bloque Markdown de contexto, o '' si el usuario no tiene memoria.
    """
    semantic_entries: list[SemanticMemoryOut] = []
    episodic_entries: list[EpisodicMemoryOut] = []
    procedural_entries: list[ProceduralMemoryOut] = []

    if ctx.semantic_store is not None:
        semantic_entries = await ctx.semantic_store.search(query, limit=SEMANTIC_LIMIT)

    if ctx.episodic_store is not None:
        episodic_entries = await ctx.episodic_store.search(query, limit=EPISODIC_LIMIT)

    if ctx.procedural_store is not None:
        all_proc = await ctx.procedural_store.list_all()
        # Filtrar stale y ordenar por confidence desc (decision #7 del brief).
        fresh = [e for e in all_proc if not e.stale]
        fresh.sort(key=lambda e: e.confidence, reverse=True)
        procedural_entries = fresh[:PROCEDURAL_LIMIT]

    sem_lines = _format_semantic(semantic_entries)
    epi_lines = _format_episodic(episodic_entries)
    proc_lines = _format_procedural(procedural_entries)

    sem_lines, epi_lines, proc_lines = _truncate_to_budget(
        sem_lines, epi_lines, proc_lines, budget_tokens
    )

    return _build_block(sem_lines, epi_lines, proc_lines)
