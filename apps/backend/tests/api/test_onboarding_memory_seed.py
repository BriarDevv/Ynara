"""Tests de INTEGRACIÓN del seed de memoria del onboarding (G4, ADR-026 §2).

``POST /v1/onboarding`` siembra, en la MISMA transacción que lo operativo:
- ``mood`` + ``mood_free_text`` -> 1 hecho semántico (ánimo inicial).
- ``about`` (estudia/trabaja/propósito/intereses) -> 1 hecho semántico por campo no vacío.
- ``about.dedication`` -> 1 entrada procedural.

Setup espejado de ``tests/api/test_memory_audit.py`` (``httpx.AsyncClient`` +
``ASGITransport``, override de ``get_db`` + Fakes de embedder/reranker, JWT real). Los
endpoints commitean: como el ``db_session`` corre en un savepoint, ese commit queda
consultable en la MISMA sesión y el rollback del fixture limpia.

Cobertura:
1. Full intake -> 5 hechos semánticos (descifrados) + dedicación procedural + 6 filas
   de audit con ``origin_tool="onboarding"``.
2. REGLA #4: las filas de audit del seed llevan el marcador nuevo y NO contienen el
   plaintext; ``record_hash`` es sha256 hex.
3. Idempotencia (re-onboarding): el segundo POST no duplica memoria (dedupe por hash +
   upsert por key).
4. Sin señales memory-bound -> 0 sembrado, lo operativo igual persiste.
5. Señales parciales (free-text de ánimo + un solo campo de "sobre vos", sin dedicación).
6. Best-effort: si el embedder falla, lo semántico se saltea pero el onboarding y la
   dedicación procedural (no embeddea) persisten igual.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_embedder, get_reranker
from app.core.security import create_access_token
from app.enums import AuditOperation, MemoryLayer
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.reranker import FakeReranker
from app.main import app
from app.memory.procedural import ProceduralMemoryStore
from app.memory.semantic import SemanticMemoryStore
from app.models.audit import AuditLog
from app.models.user import User
from app.services.onboarding_seed import DEDICATION_KEY, ONBOARDING_AUDIT_ORIGIN

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Embedder que siempre falla (best-effort del seed)
# ---------------------------------------------------------------------------


class _FailingEmbedder:
    """Embedder que siempre falla — prueba que el seed semántico es best-effort."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedder caido")


# ---------------------------------------------------------------------------
# Helpers (flush, NO commit — el rollback del fixture limpia)
# ---------------------------------------------------------------------------


def _intake(**overrides: object) -> dict[str, object]:
    """Body válido del intake con mood + sobre-vos completos; ``overrides`` pisa claves."""
    body: dict[str, object] = {
        "display_name": "Mateo",
        "interested_modes": ["productividad", "estudio"],
        "a11y": {"text_size": "md", "high_contrast": False, "motion": "auto"},
        "mood": ["tranqui"],
        "mood_free_text": "arrancando el dia",
        "about": {
            "dedication": "ambos",
            "study_what": "ingenieria",
            "work_what": "freelance",
            "purpose": "organizarme",
            "interests": "musica, running",
        },
    }
    body.update(overrides)
    return body


async def _seed_user(session: AsyncSession) -> User:
    """Inserta un User mínimo (flush). La FK de las tablas sagradas exige un user real."""
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession, *, failing_embedder: bool = False) -> httpx.AsyncClient:
    """Overridea ``get_db`` + Fakes (el lifespan no corre bajo ASGITransport).

    Con ``failing_embedder=True`` el embedder inyectado siempre falla (best-effort).
    """
    embedder: object = _FailingEmbedder() if failing_embedder else FakeEmbeddingClient()

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_reranker] = lambda: FakeReranker()
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _read_stores(
    db_session: AsyncSession, user_id: uuid.UUID
) -> tuple[SemanticMemoryStore, ProceduralMemoryStore]:
    """Stores para releer la memoria sembrada (semantic.list_all descifra)."""
    embedder = FakeEmbeddingClient()
    reranker = FakeReranker()
    return (
        SemanticMemoryStore(db_session, user_id, embedder, reranker),
        ProceduralMemoryStore(db_session, user_id),
    )


async def _audit_rows(session: AsyncSession, user_id: uuid.UUID) -> list[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.user_id == user_id).order_by(AuditLog.created_at)
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# 1. Full intake -> hechos semánticos + dedicación procedural + audit
# ---------------------------------------------------------------------------


async def test_seed_writes_semantic_facts_and_procedural_dedication(
    db_session: AsyncSession,
) -> None:
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post("/v1/onboarding", headers=_bearer(user.id), json=_intake())
        assert resp.status_code == 200

        semantic, procedural = _read_stores(db_session, user.id)

        # 5 hechos semánticos: 1 de ánimo + 4 de "sobre vos".
        assert await semantic.count() == 5
        facts = " || ".join(f.content for f in await semantic.list_all())
        assert "tranqui" in facts
        assert "arrancando el dia" in facts
        assert "ingenieria" in facts
        assert "freelance" in facts
        assert "organizarme" in facts
        assert "musica, running" in facts

        # Dedicación como preferencia procedural.
        dedication = await procedural.get(DEDICATION_KEY)
        assert dedication is not None
        assert dedication.value == {"dedication": "ambos"}

        # 6 filas de audit (5 semantic + 1 procedural), todas con el marcador del seed.
        rows = await _audit_rows(db_session, user.id)
        assert len(rows) == 6
        assert all(r.origin_tool == ONBOARDING_AUDIT_ORIGIN for r in rows)
        assert all(r.operation == AuditOperation.WRITE for r in rows)
        layers = [r.target_layer for r in rows]
        assert layers.count(MemoryLayer.SEMANTIC) == 5
        assert layers.count(MemoryLayer.PROCEDURAL) == 1
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. REGLA #4 — marcador nuevo + sin plaintext en audit
# ---------------------------------------------------------------------------


async def test_seed_audit_marker_and_no_plaintext(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post("/v1/onboarding", headers=_bearer(user.id), json=_intake())
        assert resp.status_code == 200

        rows = await _audit_rows(db_session, user.id)
        assert rows  # hay filas que inspeccionar
        for row in rows:
            # Marcador NUEVO: distinto del QWEN (origin_model) y del owner-edit (todo None).
            assert row.origin_tool == ONBOARDING_AUDIT_ORIGIN
            assert row.origin_model is None
            assert row.origin_mode is None
            # record_hash es sha256 hex de 64 chars.
            assert len(row.record_hash) == 64
            assert all(c in "0123456789abcdef" for c in row.record_hash)
            # El plaintext NUNCA aparece en columnas de audit (regla #4).
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
            for leak in ("ingenieria", "arrancando", "freelance", "ambos", "running"):
                assert leak not in serialized
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. Idempotencia: re-onboarding no duplica memoria
# ---------------------------------------------------------------------------


async def test_seed_is_idempotent_on_reonboarding(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            first = await client.post("/v1/onboarding", headers=_bearer(user.id), json=_intake())
            assert first.status_code == 200
            second = await client.post("/v1/onboarding", headers=_bearer(user.id), json=_intake())
            assert second.status_code == 200

        semantic, procedural = _read_stores(db_session, user.id)
        # El segundo POST dedupea por hash (semantic) y upsertea por key (procedural):
        # nada se duplica.
        assert await semantic.count() == 5
        assert await procedural.count() == 1
        rows = await _audit_rows(db_session, user.id)
        assert len(rows) == 6
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3b. skip-if-seeded: re-onboarding con free-text EDITADO no duplica memoria
# ---------------------------------------------------------------------------


async def test_seed_skips_reseed_on_edited_free_text(db_session: AsyncSession) -> None:
    """El dedupe por hash NO cazaba el free-text editado (hash distinto) y agregaba un
    hecho nuevo dejando el viejo. Con skip-if-seeded, si el usuario YA tiene hechos
    semánticos del onboarding, el 2do seed NO re-siembra: la memoria semántica queda
    congelada en la del 1er onboarding (no se duplica) y NO se tocan filas sagradas.
    """
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            first = await client.post("/v1/onboarding", headers=_bearer(user.id), json=_intake())
            assert first.status_code == 200
            # Re-onboarding con free-text EDITADO (mismo usuario, misma dedicación).
            edited = await client.post(
                "/v1/onboarding",
                headers=_bearer(user.id),
                json=_intake(
                    mood_free_text="ahora con mas claridad",
                    about={
                        "dedication": "ambos",
                        "study_what": "ingenieria de sistemas",
                        "work_what": "freelance",
                        "purpose": "organizarme",
                        "interests": "musica, running",
                    },
                ),
            )
            assert edited.status_code == 200

        semantic, _procedural = _read_stores(db_session, user.id)
        # NO se duplicó: siguen los 5 hechos del 1er onboarding (no 5 + los editados).
        assert await semantic.count() == 5
        facts = " || ".join(f.content for f in await semantic.list_all())
        # Quedó el texto ORIGINAL; el editado NO se sembró (memoria semántica congelada).
        assert "ingenieria de sistemas" not in facts
        assert "ahora con mas claridad" not in facts
        # Audit: solo las 6 filas del 1er seed (el 2do no agregó semánticas).
        rows = await _audit_rows(db_session, user.id)
        assert len(rows) == 6
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. Sin señales memory-bound -> 0 sembrado, operativo igual persiste
# ---------------------------------------------------------------------------


async def test_seed_skips_when_no_memory_signals(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/onboarding",
                headers=_bearer(user.id),
                json={
                    "display_name": "Ana",
                    "interested_modes": ["bienestar"],
                    "a11y": {"text_size": "lg", "high_contrast": True, "motion": "reduce"},
                },
            )
        assert resp.status_code == 200

        semantic, procedural = _read_stores(db_session, user.id)
        assert await semantic.count() == 0
        assert await procedural.count() == 0
        assert await _audit_rows(db_session, user.id) == []

        # Lo operativo igual aterrizó.
        await db_session.refresh(user)
        assert user.onboarding_completed is True
        assert user.preferences["interested_modes"] == ["bienestar"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. Señales parciales (ánimo solo free-text + un campo de sobre-vos, sin dedicación)
# ---------------------------------------------------------------------------


async def test_seed_partial_signals(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/onboarding",
                headers=_bearer(user.id),
                json=_intake(
                    mood=[],
                    mood_free_text="con energia",
                    about={"study_what": "fisica"},
                ),
            )
        assert resp.status_code == 200

        semantic, procedural = _read_stores(db_session, user.id)
        # 2 hechos: ánimo (solo free-text) + 1 campo de "sobre vos". Sin dedicación.
        assert await semantic.count() == 2
        facts = " || ".join(f.content for f in await semantic.list_all())
        assert "con energia" in facts
        assert "fisica" in facts
        assert await procedural.count() == 0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. Best-effort: embedder caído no tumba el onboarding ni la dedicación procedural
# ---------------------------------------------------------------------------


async def test_seed_best_effort_when_embedder_fails(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    client = await _client(db_session, failing_embedder=True)
    try:
        async with client:
            resp = await client.post("/v1/onboarding", headers=_bearer(user.id), json=_intake())
        # El onboarding NO se cae aunque el embedder falle.
        assert resp.status_code == 200

        semantic, procedural = _read_stores(db_session, user.id)
        # Lo semántico (embeddea) se saltea entero; la dedicación procedural (no embeddea)
        # se siembra igual -> aislamiento por savepoint.
        assert await semantic.count() == 0
        assert await procedural.count() == 1
        rows = await _audit_rows(db_session, user.id)
        assert len(rows) == 1
        assert rows[0].target_layer == MemoryLayer.PROCEDURAL

        # Lo operativo persiste pese al fallo del seed semántico.
        await db_session.refresh(user)
        assert user.onboarding_completed is True
        assert user.preferences["interested_modes"] == ["productividad", "estudio"]
    finally:
        app.dependency_overrides.clear()
