"""Tests Pydantic puros (sin DB) para el schema de audit log.

``AuditLogOut`` es el único schema público de audit (la escritura es
interna al backend, no expone payload de creación). Estos tests
verifican el strict typing y la coherencia con los enums.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.schemas.audit import AuditLogOut


def _base_payload() -> dict[str, object]:
    return {
        "id": uuid4(),
        "user_id": uuid4(),
        "operation": AuditOperation.WRITE,
        "target_layer": MemoryLayer.SEMANTIC,
        "target_id": uuid4(),
        "origin_model": LlmModel.QWEN,
        "origin_mode": Mode.PRODUCTIVIDAD,
        "origin_tool": "memory.add",
        "record_hash": "a" * 64,
        "sensitive": False,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }


class TestAuditLogOut:
    def test_valid_full_payload(self) -> None:
        m = AuditLogOut(**_base_payload())
        assert m.operation == AuditOperation.WRITE
        assert m.target_layer == MemoryLayer.SEMANTIC
        assert m.sensitive is False

    def test_nullable_fields_accepted(self) -> None:
        payload = _base_payload()
        payload.update(
            target_id=None,
            origin_model=None,
            origin_mode=None,
            origin_tool=None,
        )
        m = AuditLogOut(**payload)
        assert m.target_id is None
        assert m.origin_model is None
        assert m.origin_mode is None
        assert m.origin_tool is None

    @pytest.mark.parametrize("op", list(AuditOperation))
    def test_operation_accepts_all_enum_values(self, op: AuditOperation) -> None:
        payload = _base_payload()
        payload["operation"] = op
        m = AuditLogOut(**payload)
        assert m.operation == op

    @pytest.mark.parametrize("layer", list(MemoryLayer))
    def test_target_layer_accepts_all_enum_values(
        self, layer: MemoryLayer
    ) -> None:
        payload = _base_payload()
        payload["target_layer"] = layer
        m = AuditLogOut(**payload)
        assert m.target_layer == layer

    def test_invalid_operation_rejected(self) -> None:
        payload = _base_payload()
        payload["operation"] = "noop"  # no está en AuditOperation
        with pytest.raises(ValidationError):
            AuditLogOut(**payload)

    def test_invalid_layer_rejected(self) -> None:
        payload = _base_payload()
        payload["target_layer"] = "fictional_layer"
        with pytest.raises(ValidationError):
            AuditLogOut(**payload)

    def test_extra_field_rejected(self) -> None:
        """YnaraBaseModel.extra=forbid debe rechazar campos no declarados."""
        payload = _base_payload()
        payload["leaked_secret"] = "x"
        with pytest.raises(ValidationError):
            AuditLogOut(**payload)
