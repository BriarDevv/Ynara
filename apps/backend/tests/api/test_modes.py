"""Tests del catálogo de modos: ``GET /v1/modes``.

100% en memoria (sin DB, sin auth, sin Redis): el endpoint solo lee la config de
modos, que en los tests se inyecta vía override de ``get_available_modes`` para no
depender del loader del LLM (que valida ``LLM_SERVING``). Cubre:

1. ``build_modes_response`` (pura): shape + orden + id validado contra ``Mode``.
2. ``GET /v1/modes`` → 200 con el catálogo, en orden, sin requerir token.
3. id desconocido en la config → ``ValueError`` (fail-fast; ``Mode(id)`` levanta).
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
from httpx import ASGITransport

from app.api.v1.modes import ModesResponse, build_modes_response, get_available_modes
from app.enums import Mode
from app.llm.config import ModeConfig
from app.main import app


def _mode(name: str, model: str, layers: list[str], tools: list[str], tone: str) -> ModeConfig:
    return ModeConfig(name=name, model=model, memory_layers=layers, tools_enabled=tools, tone=tone)


# Modos fake con los 5 ids REALES (valida que todos los miembros de ``Mode`` se
# aceptan) en orden de declaración (valida que el builder lo preserva).
_FAKE_MODES: dict[str, ModeConfig] = {
    "productividad": _mode(
        "productividad",
        "qwen-3.5-9b",
        ["semantic", "episodic"],
        ["calendar", "reminder", "memory"],
        "neutro-eficaz",
    ),
    "estudio": _mode("estudio", "gemma-4-12b", ["episodic", "procedural"], [], "encouragement"),
    "bienestar": _mode(
        "bienestar", "gemma-4-12b", ["procedural", "semantic"], [], "casual-empatico"
    ),
    "vida": _mode("vida", "gemma-4-12b", ["procedural"], [], "casual-rioplatense"),
    "memoria": _mode(
        "memoria",
        "qwen-3.5-9b",
        ["episodic", "semantic", "procedural"],
        ["memory"],
        "neutro-eficaz",
    ),
}


# ---------- builder puro ----------


def test_build_modes_response_preserves_order_and_shape() -> None:
    resp = build_modes_response(_FAKE_MODES)
    assert isinstance(resp, ModesResponse)
    assert [m.id for m in resp.modes] == [Mode(k) for k in _FAKE_MODES]

    prod = resp.modes[0]
    assert prod.id == Mode.PRODUCTIVIDAD
    assert prod.model == "qwen-3.5-9b"
    assert prod.memory_layers == ["semantic", "episodic"]
    assert prod.tools_enabled == ["calendar", "reminder", "memory"]
    assert prod.tone == "neutro-eficaz"
    # Gemma (estudio) no ejecuta tools → tools_enabled vacío (ADR-002).
    assert resp.modes[1].tools_enabled == []


def test_build_modes_response_accepts_all_mode_members() -> None:
    resp = build_modes_response(_FAKE_MODES)
    assert {m.id for m in resp.modes} == set(Mode)


def test_build_modes_response_rejects_unknown_mode() -> None:
    bad = {"inexistente": _mode("inexistente", "qwen-3.5-9b", ["semantic"], [], "x")}
    with pytest.raises(ValueError):
        build_modes_response(bad)


# ---------- endpoint ----------


@pytest.fixture
def _override_modes() -> Iterator[None]:
    app.dependency_overrides[get_available_modes] = lambda: _FAKE_MODES
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_available_modes, None)


@pytest.mark.usefixtures("_override_modes")
async def test_get_modes_returns_catalog() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/modes")

    assert resp.status_code == 200
    body = resp.json()
    ids = [m["id"] for m in body["modes"]]
    assert ids == ["productividad", "estudio", "bienestar", "vida", "memoria"]
    assert body["modes"][0] == {
        "id": "productividad",
        "model": "qwen-3.5-9b",
        "memory_layers": ["semantic", "episodic"],
        "tools_enabled": ["calendar", "reminder", "memory"],
        "tone": "neutro-eficaz",
    }


@pytest.mark.usefixtures("_override_modes")
async def test_get_modes_needs_no_auth() -> None:
    # Sin header Authorization: igual 200 (endpoint público, mismo tier que /health).
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/modes")
    assert resp.status_code == 200
