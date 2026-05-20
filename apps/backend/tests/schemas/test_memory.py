"""Tests Pydantic puros (sin DB) para los schemas sagrados de memoria.

Cubre los bounds, defaults y validaciones cross-field de los schemas
de las 3 capas. NO levanta Postgres — solo construye instancias
Pydantic y verifica las validaciones declaradas. Tests de integración
con DB real van con PR C (wrappers).

Mapeo a los constraints del modelo:

- ``SemanticMemoryCreate.importance`` ``Field(ge=0, le=100)`` ↔ CHECK
  ``importance IS NULL OR BETWEEN 0 AND 100``.
- ``EpisodicMemoryCreate.retention_days`` ``Field(ge=1, le=3650)`` ↔
  CHECK ``retention_days BETWEEN 1 AND 3650``.
- ``EpisodicMemoryCreate`` model_validator ↔ CHECK
  ``retention_days_sensitive_cap`` (ADR-007 D2).
- ``ProceduralMemoryUpsert.key`` ``Field(max_length=120)`` ↔ VARCHAR(120).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.schemas.memory import (
    EpisodicMemoryCreate,
    MemorySettingsUpdate,
    ProceduralMemoryUpsert,
    SemanticMemoryCreate,
    SemanticMemoryUpdate,
)


# ---------- Semantic ----------


class TestSemanticMemoryCreate:
    def test_valid_minimal(self) -> None:
        m = SemanticMemoryCreate(content="el usuario prefiere voseo")
        assert m.content == "el usuario prefiere voseo"
        assert m.importance is None
        assert m.source_session_id is None

    def test_valid_with_importance_and_source(self) -> None:
        sid = uuid4()
        m = SemanticMemoryCreate(content="x", importance=42, source_session_id=sid)
        assert m.importance == 42
        assert m.source_session_id == sid

    def test_content_empty_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SemanticMemoryCreate(content="")

    def test_content_over_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SemanticMemoryCreate(content="x" * 4097)

    @pytest.mark.parametrize("importance", [-1, 101, 1000])
    def test_importance_out_of_range_rejected(self, importance: int) -> None:
        with pytest.raises(ValidationError):
            SemanticMemoryCreate(content="x", importance=importance)

    @pytest.mark.parametrize("importance", [0, 50, 100])
    def test_importance_inside_range_accepted(self, importance: int) -> None:
        m = SemanticMemoryCreate(content="x", importance=importance)
        assert m.importance == importance


class TestSemanticMemoryUpdate:
    def test_partial_update(self) -> None:
        m = SemanticMemoryUpdate(importance=10)
        assert m.content is None
        assert m.importance == 10

    def test_empty_update_accepted(self) -> None:
        # update parcial: todos los campos opcionales
        m = SemanticMemoryUpdate()
        assert m.content is None
        assert m.importance is None


# ---------- Episodic ----------


def _occurred_at() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


class TestEpisodicMemoryCreate:
    def test_valid_default_retention(self) -> None:
        m = EpisodicMemoryCreate(
            session_id=uuid4(),
            summary="resumen de la sesion",
            occurred_at=_occurred_at(),
        )
        assert m.is_sensitive is False
        assert m.retention_days == 365
        assert m.topics == {}

    def test_summary_empty_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EpisodicMemoryCreate(
                session_id=uuid4(),
                summary="",
                occurred_at=_occurred_at(),
            )

    @pytest.mark.parametrize("days", [0, -1, 3651, 10000])
    def test_retention_days_out_of_range_rejected(self, days: int) -> None:
        with pytest.raises(ValidationError):
            EpisodicMemoryCreate(
                session_id=uuid4(),
                summary="x",
                occurred_at=_occurred_at(),
                retention_days=days,
            )

    def test_sensitive_retention_capped_at_365(self) -> None:
        """ADR-007 D2: is_sensitive=True ⇒ retention_days ≤ 365."""
        with pytest.raises(ValidationError, match="ADR-007 D2"):
            EpisodicMemoryCreate(
                session_id=uuid4(),
                summary="x",
                occurred_at=_occurred_at(),
                is_sensitive=True,
                retention_days=366,
            )

    def test_sensitive_retention_within_cap_accepted(self) -> None:
        m = EpisodicMemoryCreate(
            session_id=uuid4(),
            summary="x",
            occurred_at=_occurred_at(),
            is_sensitive=True,
            retention_days=180,
        )
        assert m.retention_days == 180

    def test_non_sensitive_retention_can_exceed_365(self) -> None:
        """Si is_sensitive=False, el cap de 365 NO aplica — sube hasta 3650."""
        m = EpisodicMemoryCreate(
            session_id=uuid4(),
            summary="x",
            occurred_at=_occurred_at(),
            is_sensitive=False,
            retention_days=1000,
        )
        assert m.retention_days == 1000


# ---------- Procedural ----------


class TestProceduralMemoryUpsert:
    def test_valid_minimal(self) -> None:
        m = ProceduralMemoryUpsert(key="voseo", value={"enabled": True})
        assert m.key == "voseo"
        assert m.value == {"enabled": True}

    def test_key_empty_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProceduralMemoryUpsert(key="", value={})

    def test_key_over_120_chars_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProceduralMemoryUpsert(key="x" * 121, value={})


# ---------- Settings ----------


class TestMemorySettingsUpdate:
    @pytest.mark.parametrize("days", [29, 366, 1000])
    def test_retention_sensitive_out_of_range_rejected(self, days: int) -> None:
        """ADR-007 D2: retention_sensitive_days configurable en 30-365."""
        with pytest.raises(ValidationError):
            MemorySettingsUpdate(retention_sensitive_days=days)

    @pytest.mark.parametrize("days", [30, 180, 365])
    def test_retention_sensitive_within_range_accepted(self, days: int) -> None:
        m = MemorySettingsUpdate(retention_sensitive_days=days)
        assert m.retention_sensitive_days == days

    def test_empty_update_accepted(self) -> None:
        m = MemorySettingsUpdate()
        assert m.retention_sensitive_days is None


# ---------- Cross-schema invariants ----------


def test_all_create_schemas_strict_about_extra_fields() -> None:
    """YnaraBaseModel.extra=forbid debe rechazar campos no declarados."""
    with pytest.raises(ValidationError):
        SemanticMemoryCreate(content="x", garbage="should_fail")  # type: ignore[call-arg]


def test_uuid_fields_strict_typing() -> None:
    """YnaraBaseModel.strict=True debe rechazar UUIDs como int o str inválido."""
    with pytest.raises(ValidationError):
        SemanticMemoryCreate(content="x", source_session_id="not-a-uuid")  # type: ignore[arg-type]


def test_uuid_round_trip_str_to_uuid() -> None:
    """String UUID válido se acepta y se castea a UUID (modo strict ok con
    string si es un UUID válido bajo Pydantic v2)."""
    sid_str = "01234567-89ab-cdef-0123-456789abcdef"
    m = SemanticMemoryCreate(content="x", source_session_id=sid_str)
    assert m.source_session_id == UUID(sid_str)
