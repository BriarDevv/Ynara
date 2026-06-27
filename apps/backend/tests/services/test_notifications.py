"""Tests UNIT del notifier de push (PR-B, D4). Sin DB ni red.

Cubren el contrato del ``NoopNotificationDelivery``:
- ``send_many`` devuelve el conteo de tokens (despachados).
- El log NUNCA incluye el ``text`` (contenido del usuario) ni los tokens (credenciales):
  solo ``len(tokens)`` (regla #4).
- ``build_notifier()`` devuelve algo que cumple el ``NotificationDelivery`` Protocol.
"""

from __future__ import annotations

import logging

from app.services.notifications import (
    NoopNotificationDelivery,
    NotificationDelivery,
    build_notifier,
)


async def test_send_many_returns_token_count() -> None:
    """``send_many`` devuelve la cantidad de tokens."""
    notifier = NoopNotificationDelivery()
    count = await notifier.send_many(tokens=["t1", "t2", "t3"], text="recordá comprar pan")
    assert count == 3


async def test_send_many_empty_tokens_returns_zero() -> None:
    """Sin tokens, devuelve 0 (no hay a quién despachar)."""
    notifier = NoopNotificationDelivery()
    assert await notifier.send_many(tokens=[], text="x") == 0


async def test_send_many_does_not_log_text_or_tokens(caplog) -> None:  # type: ignore[no-untyped-def]
    """Regla #4: el log SOLO lleva el conteo, NUNCA el ``text`` ni los tokens."""
    notifier = NoopNotificationDelivery()
    secret_text = "secreto-medico-del-usuario"
    secret_token = "token-credencial-super-secreto"
    with caplog.at_level(logging.INFO):
        await notifier.send_many(tokens=[secret_token], text=secret_text)

    blob = caplog.text
    assert secret_text not in blob
    assert secret_token not in blob
    # El conteo SÍ aparece (observabilidad del lote).
    assert "tokens=1" in blob


def test_build_notifier_satisfies_protocol() -> None:
    """``build_notifier()`` devuelve una implementación del Protocol (hoy el noop)."""
    notifier = build_notifier()
    assert isinstance(notifier, NotificationDelivery)
    assert isinstance(notifier, NoopNotificationDelivery)
