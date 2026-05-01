"""Minimal import test for services/llm/base.py — written BEFORE implementation (TDD)."""


def test_import_abstract_llm_provider():
    """Importing AbstractLLMProvider, LLMMessage, LLMModelNotReadyError must succeed."""
    from lingosips.services.llm.base import (  # noqa: F401
        AbstractLLMProvider,
        LLMMessage,
        LLMModelNotReadyError,
    )


def test_llm_model_not_ready_error_is_exception():
    from lingosips.services.llm.base import LLMModelNotReadyError

    err = LLMModelNotReadyError("model missing")
    assert isinstance(err, Exception)
    assert str(err) == "model missing"
