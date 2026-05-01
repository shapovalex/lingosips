"""Tests for services/speech/base.py — written BEFORE implementation (TDD).

Covers AbstractSpeechProvider ABC, SyllableDetail dataclass, SyllableResult dataclass.
"""

from dataclasses import fields

import pytest

from lingosips.services.speech.base import AbstractSpeechProvider, SyllableDetail, SyllableResult


class TestSyllableDetail:
    def test_syllable_detail_fields(self):
        detail = SyllableDetail(syllable="ca", correct=True, score=0.95)
        assert detail.syllable == "ca"
        assert detail.correct is True
        assert detail.score == 0.95

    def test_syllable_detail_default_score(self):
        detail = SyllableDetail(syllable="te", correct=False)
        assert detail.score == 1.0  # default

    def test_syllable_detail_is_dataclass(self):
        field_names = {f.name for f in fields(SyllableDetail)}
        assert field_names == {"syllable", "correct", "score"}

    def test_syllable_detail_correct_false(self):
        detail = SyllableDetail(syllable="gua", correct=False, score=0.4)
        assert detail.correct is False
        assert detail.score == 0.4


class TestSyllableResult:
    def test_syllable_result_fields(self):
        result = SyllableResult(
            overall_correct=False,
            syllables=[SyllableDetail("a", True), SyllableDetail("gua", False)],
            correction_message="Stress on third syllable",
        )
        assert result.overall_correct is False
        assert len(result.syllables) == 2
        assert result.correction_message == "Stress on third syllable"

    def test_syllable_result_none_correction(self):
        result = SyllableResult(overall_correct=True, syllables=[], correction_message=None)
        assert result.correction_message is None

    def test_syllable_result_is_dataclass(self):
        field_names = {f.name for f in fields(SyllableResult)}
        assert field_names == {"overall_correct", "syllables", "correction_message"}

    def test_syllable_result_empty_syllables(self):
        result = SyllableResult(overall_correct=True, syllables=[], correction_message=None)
        assert result.syllables == []


class TestAbstractSpeechProvider:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            AbstractSpeechProvider()  # type: ignore[abstract]

    def test_has_synthesize_abstract_method(self):
        assert hasattr(AbstractSpeechProvider, "synthesize")

    def test_has_evaluate_pronunciation_abstract_method(self):
        assert hasattr(AbstractSpeechProvider, "evaluate_pronunciation")

    def test_has_provider_name_abstract_property(self):
        assert hasattr(AbstractSpeechProvider, "provider_name")

    def test_has_model_name_abstract_property(self):
        assert hasattr(AbstractSpeechProvider, "model_name")
