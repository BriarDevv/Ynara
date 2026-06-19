"""Tests del util de texto compartido de la capa LLM (``app.llm.text_utils``).

Sin DB ni red: ``split_thinking`` es una función pura. Cubre la separación del
bloque ``<think>...</think>`` (Qwen thinking model) del texto limpio, usado por el
playground admin (Fase A, ADR-018) y, vía el regex reexportado, por el motor de
memoria.
"""

from __future__ import annotations

from app.llm.text_utils import THINK_BLOCK_RE, split_thinking


def test_split_thinking_separates_block() -> None:
    """Con un <think>...</think> embebido: text limpio + thinking crudo (con tags)."""
    raw = "<think>razonando</think>Respuesta final."
    clean_text, thinking = split_thinking(raw)
    assert clean_text == "Respuesta final."
    assert thinking == "<think>razonando</think>"


def test_split_thinking_no_block_returns_none() -> None:
    """Sin <think>: thinking es None y el text vuelve recortado."""
    clean_text, thinking = split_thinking("  solo respuesta  ")
    assert clean_text == "solo respuesta"
    assert thinking is None


def test_split_thinking_multiline_block() -> None:
    """El bloque cruza saltos de línea (DOTALL) y se quita entero."""
    raw = "<think>\nlínea 1\nlínea 2\n</think>\nTexto visible."
    clean_text, thinking = split_thinking(raw)
    assert clean_text == "Texto visible."
    assert thinking is not None
    assert "línea 1" in thinking
    assert "<think>" not in clean_text


def test_split_thinking_case_insensitive_tag() -> None:
    """El tag matchea sin importar el case (IGNORECASE)."""
    clean_text, thinking = split_thinking("<THINK>x</THINK>final")
    assert clean_text == "final"
    assert thinking == "<THINK>x</THINK>"


def test_split_thinking_empty_text() -> None:
    """Texto vacío: clean vacío, thinking None (no crashea)."""
    assert split_thinking("") == ("", None)


def test_think_block_re_is_the_public_regex() -> None:
    """El regex público existe y matchea el bloque (lo reusa memory_engine)."""
    assert THINK_BLOCK_RE.search("<think>a</think>") is not None
