"""Tests de regresion de los system prompts por modo (M5).

Sin DB ni red: los prompts son strings estaticos. Verificamos invariantes
clave, no el texto entero palabra por palabra (snapshot liviano):

- ``load_prompt`` devuelve un string no vacio para los 5 modos.
- Cada prompt incluye los fragmentos compartidos de identidad / voz / seguridad.
- Los modos Gemma (estudio, bienestar, vida) NO mencionan tools ni escritura de
  memoria; los Qwen (productividad, memoria) si habilitan tools.
- ``load_prompt`` con un modo invalido levanta ``ValueError``.
- Coherencia: todos los miembros de ``Mode`` tienen prompt.
"""

from __future__ import annotations

import pytest

from app.enums import Mode
from app.llm.prompts import load_prompt
from app.llm.prompts.bienestar import SYSTEM_PROMPT as BIENESTAR_PROMPT
from app.llm.prompts.estudio import SYSTEM_PROMPT as ESTUDIO_PROMPT
from app.llm.prompts.loader import _MODE_PROMPTS
from app.llm.prompts.memoria import SYSTEM_PROMPT as MEMORIA_PROMPT
from app.llm.prompts.productividad import SYSTEM_PROMPT as PRODUCTIVIDAD_PROMPT
from app.llm.prompts.shared import (
    IDENTITY_FRAGMENT,
    SAFETY_FRAGMENT,
    VOICE_FRAGMENT,
)
from app.llm.prompts.vida import SYSTEM_PROMPT as VIDA_PROMPT

# Modos conversacionales Gemma: solo leen memoria, no escriben, no llaman tools.
_GEMMA_MODES = (Mode.ESTUDIO, Mode.BIENESTAR, Mode.VIDA)
# Modos agente Qwen: leen y escriben memoria, llaman tools.
_QWEN_MODES = (Mode.PRODUCTIVIDAD, Mode.MEMORIA)

# SYSTEM_PROMPT de modo (sin los fragmentos compartidos) para asserts de modo.
_MODE_ONLY_PROMPTS = {
    Mode.PRODUCTIVIDAD: PRODUCTIVIDAD_PROMPT,
    Mode.ESTUDIO: ESTUDIO_PROMPT,
    Mode.BIENESTAR: BIENESTAR_PROMPT,
    Mode.VIDA: VIDA_PROMPT,
    Mode.MEMORIA: MEMORIA_PROMPT,
}


@pytest.mark.parametrize("mode", list(Mode))
def test_load_prompt_returns_non_empty_string(mode: Mode) -> None:
    prompt = load_prompt(mode)
    assert isinstance(prompt, str)
    assert prompt.strip()


@pytest.mark.parametrize("mode", list(Mode))
def test_prompt_includes_shared_fragments(mode: Mode) -> None:
    """Todo prompt antepone identidad + voz + seguridad."""
    prompt = load_prompt(mode)
    assert IDENTITY_FRAGMENT in prompt
    assert VOICE_FRAGMENT in prompt
    assert SAFETY_FRAGMENT in prompt


@pytest.mark.parametrize("mode", list(Mode))
def test_prompt_carries_shared_invariants(mode: Mode) -> None:
    """Invariantes de voz del producto presentes en cada prompt ensamblado."""
    prompt = load_prompt(mode).lower()
    # Identidad: marca y al menos un pilar nombrado.
    assert "ynara" in prompt
    assert "productividad" in prompt
    assert "memoria" in prompt
    # Voz: rioplatense / voseo, sin moralizar.
    assert "rioplatense" in prompt
    assert "voseo" in prompt
    # Seguridad: perimetro de datos + honestidad ante la falta de info.
    assert "perimetro" in prompt
    assert "inventar" in prompt


def test_every_mode_has_a_prompt() -> None:
    """Coherencia: el mapa del loader cubre todos los miembros de ``Mode``."""
    assert set(_MODE_PROMPTS) == set(Mode)
    assert set(_MODE_ONLY_PROMPTS) == set(Mode)


@pytest.mark.parametrize("mode", _GEMMA_MODES)
def test_gemma_modes_do_not_enable_tools_or_memory_writes(mode: Mode) -> None:
    """Gemma solo lee: el prompt de modo no menciona tools ni escritura."""
    mode_prompt = _MODE_ONLY_PROMPTS[mode].lower()
    assert "tool" not in mode_prompt
    assert "escrib" not in mode_prompt
    # Refuerzo: estos modos se declaran como conversacion cerrada. Normalizamos
    # el whitespace porque el wrap de linea parte la frase ("...y no\nejecutas").
    normalized = " ".join(mode_prompt.split())
    assert "no ejecutas acciones externas" in normalized


@pytest.mark.parametrize("mode", _QWEN_MODES)
def test_qwen_modes_enable_tools(mode: Mode) -> None:
    """Qwen es agente: el prompt de modo habilita tools (la escritura de
    memoria la cubren test_productividad/test_memoria por separado)."""
    mode_prompt = _MODE_ONLY_PROMPTS[mode].lower()
    assert "tool" in mode_prompt


def test_productividad_mentions_memory_write() -> None:
    """Productividad (Qwen) declara que puede escribir memoria."""
    assert "escrib" in PRODUCTIVIDAD_PROMPT.lower()


def test_memoria_mentions_memory_write() -> None:
    """Memoria (Qwen) declara que puede escribir / borrar memoria."""
    text = MEMORIA_PROMPT.lower()
    assert "escrib" in text or "borrar" in text


def test_load_prompt_rejects_invalid_mode() -> None:
    """Un modo fuera del enum levanta ``ValueError``."""
    with pytest.raises(ValueError, match="system prompt"):
        load_prompt("modo-inexistente")  # type: ignore[arg-type]


def test_load_prompt_is_cached() -> None:
    """El loader cachea: misma entrada, mismo objeto string."""
    first = load_prompt(Mode.VIDA)
    second = load_prompt(Mode.VIDA)
    assert first is second
