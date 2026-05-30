"""Tests UNIT (sin DB) de la capa de memoria sagrada (M7, ADR-010).

Mockear ``AsyncSession`` está PROHIBIDO (AGENTS.md §5: los mocks de DB ocultan
bugs de migración). Por eso ``add`` / ``search`` / ``update`` / ``delete`` /
crypto round-trip / aislamiento por ``user_id`` son tests de **integración**
(contra pgvector real vía ``db_session``), no unit.

Acá viven solo las invariantes que NO tocan DB:

1. ``SemanticMemoryOut`` / ``EpisodicMemoryOut`` rechazan ``content`` / ``summary``
   en ``bytes`` crudos (``ValidationError``): es la defensa en profundidad que
   obliga al wrapper a descifrar el ``BYTEA`` ANTES de construir el schema
   (``strict=True``). Si esto fallara, un wrapper con bug devolvería el blob
   cifrado como si fuera texto.
2. El cap de retención sensible de ``EpisodicMemoryCreate`` (``is_sensitive=True``
   + ``retention_days > 365`` → ``ValueError``, ADR-007 D2): el store persiste
   ``retention_days`` tal como llega, así que esta validación debe vivir (y vive)
   en el schema, no en el store.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.memory import (
    EpisodicMemoryCreate,
    EpisodicMemoryOut,
    SemanticMemoryOut,
)


def _now() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


# ---------- los Out rechazan bytes crudos (defensa en profundidad) ----------


def test_semantic_out_rejects_raw_bytes_content() -> None:
    """``SemanticMemoryOut`` con ``content=bytes`` → ``ValidationError``.

    El wrapper DEBE descifrar el ``BYTEA`` a ``str`` antes de construir el Out;
    ``strict=True`` no coerciona ``bytes``→``str`` (ni siquiera UTF-8 válido).
    """
    with pytest.raises(ValidationError):
        SemanticMemoryOut(
            id=uuid4(),
            user_id=uuid4(),
            content=b"\x00blob-cifrado-crudo",  # type: ignore[arg-type]
            importance=None,
            source_session_id=None,
            created_at=_now(),
            updated_at=_now(),
        )


def test_semantic_out_accepts_decrypted_str_content() -> None:
    """Contrapartida: con ``content`` ya descifrado (``str``) el Out se construye."""
    out = SemanticMemoryOut(
        id=uuid4(),
        user_id=uuid4(),
        content="el usuario prefiere voseo",
        importance=42,
        source_session_id=None,
        created_at=_now(),
        updated_at=_now(),
    )
    assert out.content == "el usuario prefiere voseo"


def test_episodic_out_rejects_raw_bytes_summary() -> None:
    """``EpisodicMemoryOut`` con ``summary=bytes`` → ``ValidationError``."""
    with pytest.raises(ValidationError):
        EpisodicMemoryOut(
            id=uuid4(),
            user_id=uuid4(),
            session_id=uuid4(),
            summary=b"\x00blob-cifrado-crudo",  # type: ignore[arg-type]
            is_sensitive=False,
            retention_days=365,
            occurred_at=_now(),
            topics={},
            created_at=_now(),
            updated_at=_now(),
        )


def test_episodic_out_accepts_decrypted_str_summary() -> None:
    """Contrapartida: con ``summary`` ya descifrado (``str``) el Out se construye."""
    out = EpisodicMemoryOut(
        id=uuid4(),
        user_id=uuid4(),
        session_id=uuid4(),
        summary="resumen de la sesión",
        is_sensitive=False,
        retention_days=365,
        occurred_at=_now(),
        topics={"tema": "trabajo"},
        created_at=_now(),
        updated_at=_now(),
    )
    assert out.summary == "resumen de la sesión"


# ---------- cap de retención sensible (ADR-007 D2) ----------


def test_episodic_create_sensitive_retention_cap_rejected() -> None:
    """``is_sensitive=True`` + ``retention_days=400`` → ``ValueError`` (ADR-007 D2).

    El store escribe ``retention_days`` tal como llega; el cap vive en el schema.
    """
    with pytest.raises(ValidationError, match="ADR-007 D2"):
        EpisodicMemoryCreate(
            session_id=uuid4(),
            summary="resumen sensible",
            occurred_at=_now(),
            is_sensitive=True,
            retention_days=400,
        )


def test_episodic_create_sensitive_within_cap_accepted() -> None:
    """``is_sensitive=True`` + ``retention_days=365`` (el tope exacto) se acepta."""
    payload = EpisodicMemoryCreate(
        session_id=uuid4(),
        summary="resumen sensible",
        occurred_at=_now(),
        is_sensitive=True,
        retention_days=365,
    )
    assert payload.retention_days == 365
    assert payload.is_sensitive is True
