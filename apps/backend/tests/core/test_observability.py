"""Tests del scrubber de PII de Sentry + init_sentry (regla #4).

El scrubber se prueba como función pura. ``init_sentry`` se prueba parcheando
``sentry_sdk.init`` con un grabador: verificamos que es no-op sin DSN y que con
DSN configura ``before_send=_scrub_event`` + ``send_default_pii=False``.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings
from app.core.observability import _scrub_event, init_sentry


def _settings(**overrides: object) -> Settings:
    kwargs: dict[str, object] = {
        "_env_file": None,
        "DATABASE_URL": "postgresql://test:test@localhost/test",
        "REDIS_URL": "redis://localhost:6379/0",
        "JWT_SECRET": "x" * 40,
    }
    kwargs.update(overrides)
    return Settings(**kwargs)  # type: ignore[arg-type]


# ---------- scrubber ----------


def test_scrub_drops_request_body() -> None:
    event = {"request": {"data": {"password": "hunter2", "msg": "texto privado"}}}
    scrubbed = _scrub_event(event, {})
    assert "data" not in scrubbed["request"]


def test_scrub_drops_cookies() -> None:
    event = {"request": {"cookies": {"session": "abc"}}}
    assert "cookies" not in _scrub_event(event, {})["request"]


def test_scrub_obfuscates_sensitive_headers_case_insensitive() -> None:
    event = {
        "request": {
            "headers": {
                "Authorization": "Bearer secreto",
                "Cookie": "session=abc",
                "Content-Type": "application/json",
            }
        }
    }
    headers = _scrub_event(event, {})["request"]["headers"]
    assert headers["Authorization"] == "[scrubbed]"
    assert headers["Cookie"] == "[scrubbed]"
    assert headers["Content-Type"] == "application/json"  # no sensible: intacto


def test_scrub_obfuscates_query_string() -> None:
    event = {"request": {"query_string": "token=secreto&q=hola"}}
    assert _scrub_event(event, {})["request"]["query_string"] == "[scrubbed]"


def test_scrub_drops_user_context() -> None:
    event = {"user": {"id": "u1", "email": "a@b.com", "ip_address": "1.2.3.4"}}
    assert "user" not in _scrub_event(event, {})


def test_scrub_tolerates_missing_request() -> None:
    event = {"level": "error", "message": "boom"}
    assert _scrub_event(event, {}) == {"level": "error", "message": "boom"}


def test_scrub_tolerates_non_dict_request() -> None:
    event: dict[str, Any] = {"request": "no-soy-un-dict"}
    # No debe romper aunque la estructura no sea la esperada.
    assert _scrub_event(event, {}) == {"request": "no-soy-un-dict"}


# ---------- init_sentry ----------


def test_init_sentry_noop_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr("app.core.observability.get_settings", lambda: _settings(SENTRY_DSN=""))
    monkeypatch.setattr("app.core.observability.sentry_sdk.init", lambda **kw: calls.append(kw))

    init_sentry()
    assert calls == []  # sin DSN no se manda nada a ningún lado


def test_init_sentry_configures_scrubber_with_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "app.core.observability.get_settings",
        lambda: _settings(SENTRY_DSN="https://pub@sentry.example/1", environment="staging"),
    )
    monkeypatch.setattr("app.core.observability.sentry_sdk.init", lambda **kw: calls.append(kw))

    init_sentry()

    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["before_send"] is _scrub_event
    assert kwargs["send_default_pii"] is False
    assert kwargs["environment"] == "staging"
