"""Unit tests del resolver de IP del cliente anti-spoof (issue #151).

SIN DB (no usan el marker ``integration``): ejercen la función pura
``resolve_client_ip`` y el wrapper ``_client_ip`` (este último con un Request
falso mínimo), más el ``@model_validator`` de ``trusted_proxy_ips`` en Settings.

El caso crítico es el ANTI-SPOOFING: si el peer inmediato NO está en la allowlist
de proxies confiables, el header de IP real se IGNORA y se devuelve el peer. De lo
contrario un atacante directo spoofearía el header y se daría una IP nueva por
intento, evadiendo el rate-limit por completo (PEOR que el status quo).
"""

from __future__ import annotations

import ipaddress

import pytest
from pydantic import ValidationError
from starlette.datastructures import Headers

from app.api.v1.auth import _client_ip, _trusted_networks, resolve_client_ip
from app.core.config import Settings

_TrustedNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def _networks(*entries: str) -> tuple[_TrustedNetwork, ...]:
    """Parsea IPs/CIDRs a redes ``ipaddress`` (mismo parseo que la app, vía cache)."""
    return _trusted_networks(tuple(entries))


# ---------------------------------------------------------------------------
# resolve_client_ip — función pura (sin Request)
# ---------------------------------------------------------------------------


def test_peer_confiable_con_header_devuelve_la_ip_del_header() -> None:
    """Peer en la allowlist + header presente -> la IP real adelantada por el proxy."""
    ip = resolve_client_ip(
        "10.0.0.1",
        "203.0.113.7",
        trusted_networks=_networks("10.0.0.1"),
    )
    assert ip == "203.0.113.7"


def test_peer_cubierto_por_cidr_con_header_devuelve_la_ip_del_header() -> None:
    """Peer que cae dentro de un CIDR de la allowlist -> se confía el header."""
    ip = resolve_client_ip(
        "172.17.0.5",
        "198.51.100.42",
        trusted_networks=_networks("172.17.0.0/16"),
    )
    assert ip == "198.51.100.42"


def test_anti_spoofing_peer_no_confiable_ignora_el_header() -> None:
    """SEGURIDAD: peer fuera de la allowlist + header presente -> devuelve el PEER.

    Un atacante directo (peer no confiable) que spoofea el header NO debe poder
    darse una IP nueva por intento: se ignora el header y se cuenta por su peer real.
    """
    ip = resolve_client_ip(
        "203.0.113.99",  # peer atacante, NO en la allowlist
        "1.2.3.4",  # header spoofeado
        trusted_networks=_networks("10.0.0.0/8"),
    )
    assert ip == "203.0.113.99"


def test_peer_confiable_sin_header_cae_al_peer() -> None:
    """Peer confiable pero header ausente (proxy mal configurado) -> cae al peer.

    Nunca a un XFF crudo ni a otra fuente no confiable.
    """
    ip = resolve_client_ip(
        "10.0.0.1",
        None,
        trusted_networks=_networks("10.0.0.0/8"),
    )
    assert ip == "10.0.0.1"


def test_allowlist_vacia_ignora_cualquier_header() -> None:
    """Default (allowlist vacía) -> siempre el peer (comportamiento legacy, cero riesgo)."""
    ip = resolve_client_ip(
        "203.0.113.99",
        "1.2.3.4",
        trusted_networks=_networks(),
    )
    assert ip == "203.0.113.99"


def test_peer_unknown_devuelve_unknown() -> None:
    """Peer ``"unknown"`` (sin client info) -> ``"unknown"``, sin leer el header."""
    ip = resolve_client_ip(
        "unknown",
        "1.2.3.4",
        trusted_networks=_networks("10.0.0.0/8"),
    )
    assert ip == "unknown"


def test_peer_no_parseable_como_ip_devuelve_el_peer() -> None:
    """Peer no parseable como IP -> ante la duda no se confía: se devuelve el peer."""
    ip = resolve_client_ip(
        "no-es-una-ip",
        "1.2.3.4",
        trusted_networks=_networks("10.0.0.0/8"),
    )
    assert ip == "no-es-una-ip"


def test_header_se_strippea() -> None:
    """El valor del header se ``strip()``ea (proxies que adelantan con espacios)."""
    ip = resolve_client_ip(
        "10.0.0.1",
        "  203.0.113.7  ",
        trusted_networks=_networks("10.0.0.0/8"),
    )
    assert ip == "203.0.113.7"


def test_peer_confiable_header_vacio_cae_al_peer() -> None:
    """Peer confiable pero header VACÍO ("") -> cae al peer (no envenena la key con "")."""
    ip = resolve_client_ip("10.0.0.1", "", trusted_networks=_networks("10.0.0.0/8"))
    assert ip == "10.0.0.1"


def test_peer_confiable_header_no_es_ip_cae_al_peer() -> None:
    """Peer confiable pero header con basura (no-IP) -> cae al peer (belt-and-suspenders)."""
    ip = resolve_client_ip("10.0.0.1", "no-es-una-ip", trusted_networks=_networks("10.0.0.0/8"))
    assert ip == "10.0.0.1"


# ---------------------------------------------------------------------------
# _client_ip — wrapper sobre Request (Request falso mínimo)
# ---------------------------------------------------------------------------


class _FakeClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _FakeRequest:
    """Request falso mínimo: solo expone ``client`` y ``headers`` (lo que usa _client_ip).

    ``headers`` es un ``starlette.datastructures.Headers`` (case-insensitive, como el
    Request real) para no dar falsa cobertura con un dict plano case-sensitive.
    """

    def __init__(self, *, host: str | None, headers: dict[str, str] | None = None) -> None:
        self.client = _FakeClient(host) if host is not None else None
        self.headers = Headers(headers or {})


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    """Pisa el get_settings cacheado que usa _client_ip por uno determinista."""
    monkeypatch.setattr("app.api.v1.auth.get_settings", lambda: settings)


def _ip_settings(**overrides: object) -> Settings:
    """Settings hermético (sin .env) con base mínima válida + overrides de IP."""
    kwargs: dict[str, object] = {
        "_env_file": None,
        "DATABASE_URL": "postgresql://test:test@localhost/test",
        "REDIS_URL": "redis://localhost:6379/0",
        "JWT_SECRET": "x" * 40,
    }
    kwargs.update(overrides)
    return Settings(**kwargs)  # type: ignore[arg-type]


def test_client_ip_sin_client_devuelve_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """request.client None (sin info de peer) -> ``"unknown"``."""
    _patch_settings(monkeypatch, _ip_settings(TRUSTED_PROXY_IPS=["10.0.0.0/8"]))
    request = _FakeRequest(host=None, headers={"CF-Connecting-IP": "1.2.3.4"})
    assert _client_ip(request) == "unknown"  # type: ignore[arg-type]


def test_client_ip_peer_confiable_lee_el_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wiring real: peer confiable + header configurado presente -> la IP del header."""
    _patch_settings(monkeypatch, _ip_settings(TRUSTED_PROXY_IPS=["10.0.0.0/8"]))
    request = _FakeRequest(host="10.0.0.7", headers={"CF-Connecting-IP": "203.0.113.7"})
    assert _client_ip(request) == "203.0.113.7"  # type: ignore[arg-type]


def test_client_ip_peer_no_confiable_ignora_el_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wiring real anti-spoof: peer NO confiable -> devuelve el peer, ignora el header."""
    _patch_settings(monkeypatch, _ip_settings(TRUSTED_PROXY_IPS=["10.0.0.0/8"]))
    request = _FakeRequest(host="203.0.113.99", headers={"CF-Connecting-IP": "1.2.3.4"})
    assert _client_ip(request) == "203.0.113.99"  # type: ignore[arg-type]


def test_client_ip_default_vacio_usa_el_peer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default (TRUSTED_PROXY_IPS vacío) + header presente -> el peer (legacy)."""
    _patch_settings(monkeypatch, _ip_settings())
    request = _FakeRequest(host="203.0.113.99", headers={"CF-Connecting-IP": "1.2.3.4"})
    assert _client_ip(request) == "203.0.113.99"  # type: ignore[arg-type]


def test_client_ip_respeta_real_ip_header_custom(monkeypatch: pytest.MonkeyPatch) -> None:
    """El nombre del header es config-driven (REAL_IP_HEADER)."""
    _patch_settings(
        monkeypatch,
        _ip_settings(TRUSTED_PROXY_IPS=["10.0.0.0/8"], REAL_IP_HEADER="X-Real-IP"),
    )
    request = _FakeRequest(host="10.0.0.7", headers={"X-Real-IP": "198.51.100.42"})
    assert _client_ip(request) == "198.51.100.42"  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Settings — @model_validator de trusted_proxy_ips (fail-fast al boot)
# ---------------------------------------------------------------------------


def test_settings_rechaza_trusted_proxy_ip_invalida() -> None:
    """Una entry no parseable como IP/CIDR rompe el boot (fail-fast, anti-agujero)."""
    with pytest.raises(ValidationError, match="TRUSTED_PROXY_IPS"):
        _ip_settings(TRUSTED_PROXY_IPS=["no-es-una-ip"])


def test_settings_acepta_ip_suelta_y_cidr() -> None:
    """IPs sueltas y CIDRs válidos pasan el validador."""
    s = _ip_settings(TRUSTED_PROXY_IPS=["127.0.0.1", "10.0.0.0/8", "::1"])
    assert s.trusted_proxy_ips == ["127.0.0.1", "10.0.0.0/8", "::1"]


def test_settings_parsea_trusted_proxy_ips_csv_desde_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """CRÍTICO: ``TRUSTED_PROXY_IPS`` como CSV desde env parsea a lista (no crashea el boot).

    pydantic-settings JSON-decodea ``list[str]`` desde env ANTES de los validators; sin
    ``NoDecode`` + el ``field_validator``, ``TRUSTED_PROXY_IPS=127.0.0.1,10.0.0.0/8`` (la
    sintaxis human-friendly de .env.example) rompía el arranque. Ejerce el source REAL de
    env (no kwargs) — el path que el bug original tenía sin cubrir.
    """
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "127.0.0.1, 10.0.0.0/8")
    s = _ip_settings()
    assert s.trusted_proxy_ips == ["127.0.0.1", "10.0.0.0/8"]


def test_settings_trusted_proxy_ips_vacio_desde_env_es_lista(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``TRUSTED_PROXY_IPS=`` (vacío, lo que ships .env.example) desde env -> ``[]``, sin crash."""
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "")
    s = _ip_settings()
    assert s.trusted_proxy_ips == []
