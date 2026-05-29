"""Tests de la taxonomia de errores LLM (M1).

Verifican la jerarquia (transitorios / permanentes / semanticos) y la
garantia critica de la regla #4: ``str()`` de cualquier error NO filtra
contenido del usuario ni la respuesta del modelo.
"""

from __future__ import annotations

import pytest

from app.llm.errors import (
    LlmBadRequestError,
    LlmContextOverflowError,
    LlmError,
    LlmOverloadedError,
    LlmTimeoutError,
    LlmUnavailableError,
    MemoryRetrievalError,
    ModelNotServedError,
    ToolExecutionError,
    ToolParsingError,
    degraded_response,
)

_ALL_ERRORS = [
    LlmTimeoutError,
    LlmUnavailableError,
    LlmOverloadedError,
    LlmBadRequestError,
    LlmContextOverflowError,
    ModelNotServedError,
    ToolParsingError,
    ToolExecutionError,
    MemoryRetrievalError,
]


@pytest.mark.parametrize("error_cls", _ALL_ERRORS)
def test_all_inherit_from_llm_error(error_cls: type[LlmError]) -> None:
    assert issubclass(error_cls, LlmError)
    assert isinstance(error_cls(), LlmError)


def test_context_overflow_is_bad_request() -> None:
    """ContextOverflow es permanente: subclase de BadRequest."""
    assert issubclass(LlmContextOverflowError, LlmBadRequestError)
    assert isinstance(LlmContextOverflowError(), LlmBadRequestError)


@pytest.mark.parametrize("error_cls", _ALL_ERRORS)
def test_str_does_not_leak_user_content(error_cls: type[LlmError]) -> None:
    """Aunque se pase contenido sensible como detail, str() solo expone la
    etiqueta tecnica si no se pasa detail; y si se pasa, el caller es
    responsable. Por contrato, sin detail nunca hay contenido de usuario."""
    secret = "el usuario dijo: mi tarjeta es 4111-1111-1111-1111"
    err = error_cls()
    rendered = str(err)
    assert secret not in rendered
    assert rendered  # no vacio
    # La etiqueta es fija y tecnica.
    assert rendered == error_cls.message


def test_detail_is_optional_and_technical() -> None:
    """detail permite contexto tecnico no sensible (status HTTP, modelo)."""
    err = LlmUnavailableError("HTTP 503")
    assert "HTTP 503" in str(err)
    assert str(err).startswith(LlmUnavailableError.message)


def test_transient_vs_permanent_disjoint() -> None:
    """Un transitorio no es permanente y viceversa (sin herencia cruzada)."""
    transient = LlmTimeoutError()
    permanent = LlmBadRequestError()
    assert not isinstance(transient, LlmBadRequestError)
    assert not isinstance(permanent, (LlmTimeoutError, LlmUnavailableError))


class TestDegradedResponse:
    def test_builds_completion_result(self) -> None:
        result = degraded_response(text="no pude generar respuesta", model_name="qwen")
        assert result.finish_reason == "degraded"
        assert result.text == "no pude generar respuesta"
        assert result.tool_calls == []
        assert result.prompt_tokens == 0
        assert result.model_name == "qwen"

    def test_not_an_exception(self) -> None:
        result = degraded_response(text="x", model_name="m")
        assert not isinstance(result, Exception)
