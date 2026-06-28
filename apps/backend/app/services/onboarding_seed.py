"""Seed de memoria desde el intake del onboarding (G4, ADR-026 §2).

Convierte las señales **memory-bound** del onboarding en memoria del moat. El
endpoint operativo (``POST /v1/onboarding``) persiste lo operativo (display_name +
preferences) y, en la MISMA transacción, llama acá para sembrar:

- ``mood`` + ``mood_free_text`` -> **1 hecho semántico** ("ánimo inicial").
- ``about`` (estudia / trabaja / propósito / intereses) -> **un hecho semántico por
  campo no vacío** (criterio "un hecho por op" del extractor de memoria).
- ``about.dedication`` -> **1 entrada procedural** (preferencia estructurada).

Routing fijado por ADR-026 §2: lo operativo va a ``users`` (NO acá); a memoria solo
"quién es el usuario". Modos y a11y NUNCA entran a memoria (ensucian el recall).

SAGRADO (regla #3): escribe en ``semantic_memory`` / ``procedural_memory`` /
``audit_log``. Este módulo NO edita las tablas ni los stores sagrados — **reusa las
primitivas existentes** (``SemanticMemoryStore.add`` / ``ProceduralMemoryStore.upsert``
/ ``AuditStore.record``), así que no hay migración del schema sagrado (ADR-026).

REGLA #4: el contenido del usuario viaja al store, que lo **cifra** (semantic) antes
de persistir; ``audit_log`` solo guarda el ``record_hash`` (sha256), nunca el texto.
Ningún contenido va a logs.

Idempotencia (ADR-026 §4): re-onboarding NO duplica memoria.
- **procedural**: ``upsert`` por ``key`` (ON CONFLICT) -> una sola fila.
- **semantic**: no hay columna de hash y el ``content`` va cifrado, pero el
  ``record_hash`` (sha256 del contenido) YA vive en ``audit_log``. El dedupe consulta
  ``audit_log`` filtrando por el marcador del seed (``origin_tool``) -> no re-siembra
  lo ya sembrado, sin descifrar nada.

Atomicidad: corre dentro de la transacción del endpoint (un solo ``commit`` al
final). Cada op + su fila de audit van en un ``begin_nested()`` (SAVEPOINT), espejo
de ``apply_ops``: un fallo del embedder NO envenena la transacción ni tumba el
onboarding operativo (best-effort).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditOperation, MemoryLayer
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.memory.audit import AuditStore
from app.memory.hashing import compute_record_hash, procedural_hash_payload
from app.memory.procedural import ProceduralMemoryStore
from app.memory.semantic import SemanticMemoryStore
from app.models.audit import AuditLog
from app.schemas.memory import ProceduralMemoryUpsert, SemanticMemoryCreate
from app.schemas.onboarding import AboutYou, OnboardingIntake

logger = logging.getLogger(__name__)

# Marcador de origen NUEVO para ``audit_log`` (ADR-026 §2): distingue el seed del
# onboarding de la consolidación (``origin_model=QWEN``) y de los edits del dueño por
# HTTP (``origin_*`` todos ``None``). ``origin_tool`` es ``String(80)`` libre -> sin
# enum ni migración. También es la llave del dedupe semántico (ver ``_already_seeded``).
ONBOARDING_AUDIT_ORIGIN = "onboarding"

# Key procedural de la dedicación. Idempotente por key (``upsert`` ON CONFLICT).
# Namespaced para dejar la provenance clara y no colisionar con keys que Qwen pudiera
# inventar en la consolidación.
DEDICATION_KEY = "onboarding.dedication"


@dataclass(frozen=True)
class SeedCounts:
    """Cuántos registros sembró el seed (ops EFECTIVAS, sin contar los dedupe-skip)."""

    semantic: int
    procedural: int


def _mood_fact(mood: list[str], mood_free_text: str | None) -> str | None:
    """Un (1) hecho semántico free-text del ánimo inicial, o ``None`` si no hay señal."""
    moods = [m.strip() for m in mood if m.strip()]
    free = (mood_free_text or "").strip()
    if not moods and not free:
        return None
    if moods:
        fact = f"Al iniciar el onboarding, el usuario se sentía: {', '.join(moods)}."
    else:
        fact = "Al iniciar el onboarding, el usuario compartió cómo se sentía."
    if free:
        fact += f" En sus palabras: '{free}'."
    return fact


def _about_facts(about: AboutYou | None) -> list[str]:
    """Hechos semánticos de "sobre vos": uno por campo no vacío (0..4)."""
    if about is None:
        return []
    facts: list[str] = []
    if about.study_what.strip():
        facts.append(f"El usuario estudia {about.study_what.strip()}.")
    if about.work_what.strip():
        facts.append(f"El usuario trabaja en {about.work_what.strip()}.")
    if about.purpose.strip():
        facts.append(f"El usuario quiere usar Ynara para {about.purpose.strip()}.")
    if about.interests.strip():
        facts.append(f"Al usuario le interesan: {about.interests.strip()}.")
    return facts


def _semantic_facts(intake: OnboardingIntake) -> list[str]:
    """Todos los hechos semánticos a sembrar: ánimo inicial (0..1) + sobre vos (0..4)."""
    facts: list[str] = []
    mood = _mood_fact(intake.mood, intake.mood_free_text)
    if mood is not None:
        facts.append(mood)
    facts.extend(_about_facts(intake.about))
    return facts


async def _already_seeded(
    session: AsyncSession,
    user_id: UUID,
    layer: MemoryLayer,
    record_hash: str,
) -> bool:
    """¿Ya hay una fila de audit del seed con este ``record_hash``? (dedupe por hash).

    El seed no tiene columna de hash en las tablas sagradas (semantic va cifrado), pero
    el ``record_hash`` (sha256 del contenido) YA vive en ``audit_log``. Filtra por el
    marcador del seed (``origin_tool``) para no chocar con hashes de la consolidación.
    REGLA #4: no descifra nada — solo compara digests.
    """
    stmt = (
        select(AuditLog.id)
        .where(
            AuditLog.user_id == user_id,
            AuditLog.target_layer == layer,
            AuditLog.origin_tool == ONBOARDING_AUDIT_ORIGIN,
            AuditLog.record_hash == record_hash,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).first() is not None


async def _seed_semantic(
    session: AsyncSession,
    semantic_store: SemanticMemoryStore,
    audit_store: AuditStore,
    content: str,
    record_hash: str,
) -> bool:
    """Inserta UN hecho semántico + su fila de audit en un SAVEPOINT (atómico-o-nada).

    Best-effort: si embed/insert/audit falla, el savepoint revierte la op y se loguea
    SIN contenido (regla #4); el onboarding no se cae. Devuelve ``True`` si sembró.
    """
    try:
        async with session.begin_nested():
            out = await semantic_store.add(
                SemanticMemoryCreate(content=content, source_session_id=None)
            )
            await audit_store.record(
                operation=AuditOperation.WRITE,
                target_layer=MemoryLayer.SEMANTIC,
                target_id=out.id,
                record_hash=record_hash,
                origin_tool=ONBOARDING_AUDIT_ORIGIN,
                sensitive=False,
            )
        return True
    except Exception:
        logger.warning("onboarding_seed: hecho semántico revertido (savepoint), skip")
        return False


async def _seed_dedication(
    session: AsyncSession,
    procedural_store: ProceduralMemoryStore,
    audit_store: AuditStore,
    value: dict[str, str],
    record_hash: str,
) -> bool:
    """Upsert de la dedicación (procedural) + su fila de audit en un SAVEPOINT.

    Idempotente por key (ON CONFLICT). Best-effort igual que ``_seed_semantic``.
    """
    try:
        async with session.begin_nested():
            out = await procedural_store.upsert(
                ProceduralMemoryUpsert(key=DEDICATION_KEY, value=value)
            )
            await audit_store.record(
                operation=AuditOperation.WRITE,
                target_layer=MemoryLayer.PROCEDURAL,
                target_id=out.id,
                record_hash=record_hash,
                origin_tool=ONBOARDING_AUDIT_ORIGIN,
                sensitive=False,
            )
        return True
    except Exception:
        logger.warning("onboarding_seed: dedicación procedural revertida (savepoint), skip")
        return False


async def seed_onboarding_memory(
    *,
    session: AsyncSession,
    user_id: UUID,
    intake: OnboardingIntake,
    embedder: EmbeddingClient,
    reranker: Reranker,
) -> SeedCounts:
    """Siembra memoria semántica + procedural desde el intake (best-effort, sagrado).

    Corre dentro de la transacción del endpoint (que commitea al final). Construye los
    stores ligados al ``user_id`` (aislamiento estructural), arma los hechos y la
    preferencia de dedicación, deduplica por hash contra ``audit_log`` y aplica cada op
    en su propio SAVEPOINT. NUNCA propaga: un fallo de una op se salta, el resto sigue.

    Devuelve ``SeedCounts`` con las ops EFECTIVAS (lo skippeado por dedupe no cuenta).
    """
    # Flush de lo operativo (pendiente en la sesión) ANTES de abrir savepoints: un
    # rollback de savepoint por-op no debe revertir el write operativo del endpoint.
    await session.flush()

    semantic_store = SemanticMemoryStore(session, user_id, embedder, reranker)
    procedural_store = ProceduralMemoryStore(session, user_id)
    audit_store = AuditStore(session, user_id)

    semantic_seeded = 0
    for content in _semantic_facts(intake):
        record_hash = compute_record_hash(content)
        if await _already_seeded(session, user_id, MemoryLayer.SEMANTIC, record_hash):
            continue
        if await _seed_semantic(session, semantic_store, audit_store, content, record_hash):
            semantic_seeded += 1

    procedural_seeded = 0
    dedication = intake.about.dedication if intake.about else None
    if dedication is not None:
        value: dict[str, str] = {"dedication": dedication}
        record_hash = compute_record_hash(procedural_hash_payload(DEDICATION_KEY, value))
        if not await _already_seeded(session, user_id, MemoryLayer.PROCEDURAL, record_hash):
            if await _seed_dedication(session, procedural_store, audit_store, value, record_hash):
                procedural_seeded += 1

    return SeedCounts(semantic=semantic_seeded, procedural=procedural_seeded)
