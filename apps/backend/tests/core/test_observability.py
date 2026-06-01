"""Tests del scrubber de PII de Sentry + init_sentry (regla #4).

El scrubber se prueba como función pura. ``init_sentry`` se prueba parcheando
``sentry_sdk.init`` con un grabador: verificamos que es no-op sin DSN y que con
DSN configura ``before_send=_scrub_event`` + ``send_default_pii=False``.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core import observability
from app.core.config import Settings
from app.core.observability import _scrub_event, init_sentry


@pytest.fixture(autouse=True)
def _reset_sentry_init_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    # ``init_sentry`` usa un flag de módulo para ser idempotente; lo reseteamos
    # antes de cada test para que el estado no se filtre entre casos.
    monkeypatch.setattr(observability, "_initialized", False)


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


def test_scrub_drops_server_name() -> None:
    # Hostname del nodo on-prem: dato de infra, no debe salir.
    event = {"server_name": "ynara-prod-node-01"}
    assert "server_name" not in _scrub_event(event, {})


def test_scrub_works_on_transaction_event() -> None:
    # Los eventos de transacción (tracing) también pasan por el scrubber
    # (before_send_transaction): mismo limpiado de PII.
    event = {
        "type": "transaction",
        "transaction": "/v1/users/{id}",
        "request": {"data": {"x": 1}, "query_string": "token=secreto"},
        "user": {"id": "u1"},
        "server_name": "node-01",
    }
    scrubbed = _scrub_event(event, {})
    assert "data" not in scrubbed["request"]
    assert scrubbed["request"]["query_string"] == "[scrubbed]"
    assert "user" not in scrubbed
    assert "server_name" not in scrubbed


def test_scrub_tolerates_missing_request() -> None:
    event = {"level": "error", "message": "boom"}
    assert _scrub_event(event, {}) == {"level": "error", "message": "boom"}


def test_scrub_tolerates_non_dict_request() -> None:
    event: dict[str, Any] = {"request": "no-soy-un-dict"}
    # No debe romper aunque la estructura no sea la esperada.
    assert _scrub_event(event, {}) == {"request": "no-soy-un-dict"}


def test_scrub_obfuscates_breadcrumbs_message_and_data() -> None:
    # Formato canónico de Sentry: {"values": [crumb, ...]}.
    event = {
        "breadcrumbs": {
            "values": [
                {"category": "query", "message": "SELECT * FROM users WHERE email='a@b.com'"},
                {"category": "rpc", "data": {"args": ["secreto"]}},
                {"category": "navigation"},  # sin message ni data: intacto
            ]
        }
    }
    crumbs = _scrub_event(event, {})["breadcrumbs"]["values"]
    assert crumbs[0]["message"] == "[scrubbed]"
    assert crumbs[0]["category"] == "query"  # metadato no sensible: intacto
    assert crumbs[1]["data"] == "[scrubbed]"
    assert crumbs[2] == {"category": "navigation"}


def test_scrub_obfuscates_breadcrumbs_as_bare_list() -> None:
    # Algunos paths pasan los breadcrumbs como lista directa, no envueltos.
    event: dict[str, Any] = {
        "breadcrumbs": [{"message": "dato privado", "data": {"x": 1}}],
    }
    crumb = _scrub_event(event, {})["breadcrumbs"][0]
    assert crumb["message"] == "[scrubbed]"
    assert crumb["data"] == "[scrubbed]"


def test_scrub_obfuscates_exception_value_preserving_type_and_stacktrace() -> None:
    # ``value`` (str(exc)) puede traer PII -> se ofusca; type y stacktrace quedan.
    event = {
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": "usuario a@b.com con token secreto",
                    "stacktrace": {"frames": [{"function": "do_thing"}]},
                }
            ]
        }
    }
    exc = _scrub_event(event, {})["exception"]["values"][0]
    assert exc["value"] == "[scrubbed]"
    assert exc["type"] == "ValueError"  # tipo preservado para diagnóstico
    assert exc["stacktrace"] == {"frames": [{"function": "do_thing"}]}


def test_scrub_drops_contexts_and_extra() -> None:
    event = {
        "contexts": {"trace": {"trace_id": "x"}, "device": {"name": "laptop-cliente"}},
        "extra": {"payload": {"msg": "contenido de usuario"}},
        "level": "error",
    }
    scrubbed = _scrub_event(event, {})
    assert "contexts" not in scrubbed
    assert "extra" not in scrubbed
    assert scrubbed["level"] == "error"  # lo demás intacto


def test_scrub_tolerates_malformed_breadcrumbs_and_exception() -> None:
    # Tipos inesperados no deben romper (defensivo, como el resto del scrubber).
    event: dict[str, Any] = {
        "breadcrumbs": "no-soy-ni-dict-ni-lista",
        "exception": ["tampoco-soy-un-dict"],
    }
    assert _scrub_event(event, {}) == {
        "breadcrumbs": "no-soy-ni-dict-ni-lista",
        "exception": ["tampoco-soy-un-dict"],
    }


def test_scrub_tolerates_non_dict_items_in_collections() -> None:
    # Breadcrumbs / exception values con elementos no-dict: se saltean sin romper.
    event: dict[str, Any] = {
        "breadcrumbs": {"values": ["soy-un-string", None]},
        "exception": {"values": ["string", 42]},
    }
    scrubbed = _scrub_event(event, {})
    assert scrubbed["breadcrumbs"]["values"] == ["soy-un-string", None]
    assert scrubbed["exception"]["values"] == ["string", 42]


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
    assert kwargs["before_send_transaction"] is _scrub_event  # también scrubea trazas
    assert kwargs["send_default_pii"] is False
    assert kwargs["environment"] == "staging"


def test_init_sentry_is_idempotent_with_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    # Reimport / uvicorn --reload re-ejecutan init_sentry a import-time: la
    # segunda llamada debe ser no-op (sentry_sdk.init no es idempotente).
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "app.core.observability.get_settings",
        lambda: _settings(SENTRY_DSN="https://pub@sentry.example/1"),
    )
    monkeypatch.setattr("app.core.observability.sentry_sdk.init", lambda **kw: calls.append(kw))

    init_sentry()
    init_sentry()
    init_sentry()

    assert len(calls) == 1  # solo la primera llamada inicializa


def test_init_sentry_noop_without_dsn_does_not_block_later_init(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Una llamada sin DSN (dev) no debe consumir el guard: si después aparece un
    # DSN, init_sentry todavía tiene que poder inicializar.
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr("app.core.observability.sentry_sdk.init", lambda **kw: calls.append(kw))

    monkeypatch.setattr("app.core.observability.get_settings", lambda: _settings(SENTRY_DSN=""))
    init_sentry()
    assert calls == []

    monkeypatch.setattr(
        "app.core.observability.get_settings",
        lambda: _settings(SENTRY_DSN="https://pub@sentry.example/1"),
    )
    init_sentry()
    assert len(calls) == 1
