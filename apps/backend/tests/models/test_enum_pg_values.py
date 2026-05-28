"""Tests sin DB de la serialización de enums a tipos PostgreSQL nativos.

Cada columna ``Enum`` de los modelos debe materializar el tipo PG con los
``.value`` (minúscula) de cada StrEnum, no con los nombres de miembro
(mayúscula). Si falta ``values_callable=enum_values`` en algún ``Enum(...)``,
el tipo PG quedaría con labels en mayúscula y los inserts del ORM romperían
con "invalid input value for enum". Ver ``app/enums.py`` y ``docs/MODELS.md``.
"""

from __future__ import annotations

from sqlalchemy import Enum as SAEnum, Table

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.models.audit import AuditLog
from app.models.session import ChatSession


def _pg_labels(table: Table, column: str) -> list[str]:
    col_type = table.c[column].type
    assert isinstance(col_type, SAEnum)
    return list(col_type.enums)


def test_session_mode_uses_enum_values() -> None:
    assert _pg_labels(ChatSession.__table__, "mode") == [m.value for m in Mode]


def test_audit_operation_uses_enum_values() -> None:
    assert _pg_labels(AuditLog.__table__, "operation") == [
        m.value for m in AuditOperation
    ]


def test_audit_target_layer_uses_enum_values() -> None:
    assert _pg_labels(AuditLog.__table__, "target_layer") == [
        m.value for m in MemoryLayer
    ]


def test_audit_origin_model_uses_enum_values() -> None:
    assert _pg_labels(AuditLog.__table__, "origin_model") == [m.value for m in LlmModel]


def test_audit_origin_mode_reuses_mode_enum_values() -> None:
    assert _pg_labels(AuditLog.__table__, "origin_mode") == [m.value for m in Mode]


def test_labels_are_lowercase_not_member_names() -> None:
    """Guard explícito contra la regresión nombres-vs-values."""
    labels = _pg_labels(ChatSession.__table__, "mode")
    assert "productividad" in labels
    assert "PRODUCTIVIDAD" not in labels
