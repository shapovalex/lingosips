"""Tests for core/practice.py — write-mode answer evaluation.

TDD: these tests are written BEFORE implementation to drive core/practice.py.
AC: 1, 2, 3
"""

from unittest.mock import AsyncMock

import pytest

from lingosips.services.llm.base import AbstractLLMProvider

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_card(target_word: str = "hola", translation: str | None = "hello"):
    """Create a minimal Card-like object for testing (no DB required)."""
    from lingosips.db.models import Card

    card = Card(id=1, target_word=target_word, translation=translation, target_language="es")
    return card


def _make_llm(response: str = "Missing the accent mark.") -> AsyncMock:
    """Return a mock AbstractLLMProvider that returns the given response."""
    mock = AsyncMock(spec=AbstractLLMProvider)
    mock.complete = AsyncMock(return_value=response)
    return mock


# ── TestCharDiff ──────────────────────────────────────────────────────────────


class TestCharDiff:
    """Tests for _char_diff(user_answer, correct_value) -> list[CharHighlight]."""

    def test_exact_match_returns_all_correct_chars(self) -> None:
        """When user_answer == correct_value, all chars are correct=True.

        The is_correct branch in evaluate_answer returns [] directly,
        but _char_diff itself marks all chars as correct when strings match.
        """
        from lingosips.core.practice import _char_diff

        result = _char_diff("hola", "hola")
        assert all(h.correct for h in result)
        assert [h.char for h in result] == list("hola")

    def test_all_wrong_chars_marked_false(self) -> None:
        """Fully different answer → all user chars are correct=False."""
        from lingosips.core.practice import _char_diff

        result = _char_diff("xyz", "abc")
        # All user chars should be marked wrong (replace/delete)
        assert all(not h.correct for h in result)
        # All user's chars appear in result
        assert [h.char for h in result] == list("xyz")

    def test_partial_match_marks_correct_and_wrong(self) -> None:
        """Mixed answer → correct chars stay green, wrong chars go red."""
        from lingosips.core.practice import _char_diff

        # "holla" vs "hola" — 'h','o','l' match; extra 'l' is wrong; 'a' matches
        result = _char_diff("holla", "hola")
        chars_in_result = [h.char for h in result]
        # All user's typed chars appear in result
        assert chars_in_result == list("holla")
        # At least some correct and some wrong
        has_correct = any(h.correct for h in result)
        has_wrong = any(not h.correct for h in result)
        assert has_correct
        assert has_wrong

    def test_empty_user_answer_returns_empty_list(self) -> None:
        """Empty user_answer → empty result (nothing to display)."""
        from lingosips.core.practice import _char_diff

        result = _char_diff("", "hola")
        assert result == []

    def test_extra_chars_at_end_are_marked_wrong(self) -> None:
        """User typed correct word plus extra chars — extras are wrong."""
        from lingosips.core.practice import _char_diff

        result = _char_diff("holaaa", "hola")
        chars = [h.char for h in result]
        assert chars == list("holaaa")
        # First 4 should be correct
        assert all(h.correct for h in result[:4])
        # Extra 'aa' should be wrong
        assert all(not h.correct for h in result[4:])

    def test_case_difference_does_not_mark_correct_chars_wrong(self) -> None:
        """Upper-case version of a matching char must NOT be marked wrong.

        Case-insensitive comparison is used for alignment so 'H' in 'Hola'
        aligns with 'h' in 'hola' and is marked correct=True.
        Original case is preserved in the display char.
        """
        from lingosips.core.practice import _char_diff

        result = _char_diff("Hola", "hola")
        # All chars should be correct — same word, different case
        assert all(h.correct for h in result)
        # Original case preserved in display
        assert [h.char for h in result] == list("Hola")

    def test_near_miss_with_case_difference_only_marks_wrong_char(self) -> None:
        """'Holb' vs 'hola': only 'b' should be wrong, not 'H' (case only differs)."""
        from lingosips.core.practice import _char_diff

        result = _char_diff("Holb", "hola")
        char_map = {h.char: h.correct for h in result}
        # 'b' is genuinely wrong (≠ 'a')
        assert char_map.get("b") is False
        # 'H' matches 'h' case-insensitively — must NOT be marked wrong
        assert char_map.get("H") is True


# ── TestEvaluateAnswer ────────────────────────────────────────────────────────


@pytest.mark.anyio
class TestEvaluateAnswer:
    """Tests for evaluate_answer(card, user_answer, llm) -> EvaluationResult."""

    async def test_exact_match_is_correct_no_llm_call(self) -> None:
        """Exact match → is_correct=True, LLM never called, highlighted_chars=[]."""
        from lingosips.core.practice import evaluate_answer

        card = _make_card(translation="hello")
        llm = _make_llm()

        result = await evaluate_answer(card, "hello", llm)

        assert result.is_correct is True
        assert result.highlighted_chars == []
        assert result.explanation is None
        assert result.correct_value == "hello"
        llm.complete.assert_not_called()

    async def test_case_insensitive_match_is_correct(self) -> None:
        """'Hola' == 'hola' (case-insensitive) → is_correct=True."""
        from lingosips.core.practice import evaluate_answer

        card = _make_card(translation="hola")
        llm = _make_llm()

        result = await evaluate_answer(card, "HOLA", llm)

        assert result.is_correct is True
        llm.complete.assert_not_called()

    async def test_whitespace_trimmed_before_compare(self) -> None:
        """Leading/trailing whitespace stripped → '  yes  ' matches 'yes'."""
        from lingosips.core.practice import evaluate_answer

        card = _make_card(translation="yes")
        llm = _make_llm()

        result = await evaluate_answer(card, "  yes  ", llm)

        assert result.is_correct is True
        llm.complete.assert_not_called()

    async def test_wrong_answer_calls_llm_for_explanation(self) -> None:
        """Wrong answer → LLM called; explanation is populated from LLM response."""
        from lingosips.core.practice import evaluate_answer

        card = _make_card(translation="hello")
        llm = _make_llm("Wrong vowel — 'hello' not 'helo'.")

        result = await evaluate_answer(card, "helo", llm)

        assert result.is_correct is False
        assert result.explanation == "Wrong vowel — 'hello' not 'helo'."
        llm.complete.assert_called_once()

    async def test_wrong_answer_suggested_rating_is_1(self) -> None:
        """Wrong answer → suggested_rating=1 (Again)."""
        from lingosips.core.practice import evaluate_answer

        card = _make_card(translation="hello")
        llm = _make_llm()

        result = await evaluate_answer(card, "helo", llm)

        assert result.suggested_rating == 1

    async def test_correct_answer_suggested_rating_is_3(self) -> None:
        """Correct answer → suggested_rating=3 (Good)."""
        from lingosips.core.practice import evaluate_answer

        card = _make_card(translation="hello")
        llm = _make_llm()

        result = await evaluate_answer(card, "hello", llm)

        assert result.suggested_rating == 3

    async def test_llm_timeout_returns_no_explanation(self) -> None:
        """asyncio.TimeoutError from LLM → explanation=None, session continues."""
        from lingosips.core.practice import evaluate_answer

        card = _make_card(translation="hello")
        llm = _make_llm()
        llm.complete = AsyncMock(side_effect=TimeoutError())

        result = await evaluate_answer(card, "helo", llm)

        assert result.is_correct is False
        assert result.explanation is None
        assert result.suggested_rating == 1  # still wrong

    async def test_llm_error_returns_no_explanation(self) -> None:
        """Generic Exception from LLM → explanation=None, session continues."""
        from lingosips.core.practice import evaluate_answer

        card = _make_card(translation="hello")
        llm = _make_llm()
        llm.complete = AsyncMock(side_effect=Exception("LLM unavailable"))

        result = await evaluate_answer(card, "helo", llm)

        assert result.is_correct is False
        assert result.explanation is None

    async def test_card_with_null_translation_treats_empty_as_correct(self) -> None:
        """Card with translation=None → correct_value='', only empty answer is correct."""
        from lingosips.core.practice import evaluate_answer

        card = _make_card(translation=None)
        llm = _make_llm()

        result_correct = await evaluate_answer(card, "", llm)
        assert result_correct.is_correct is True
        assert result_correct.correct_value == ""

        result_wrong = await evaluate_answer(card, "anything", llm)
        assert result_wrong.is_correct is False

    async def test_wrong_answer_highlighted_chars_populated(self) -> None:
        """Wrong answer → highlighted_chars list contains user's chars."""
        from lingosips.core.practice import evaluate_answer

        card = _make_card(translation="hello")
        llm = _make_llm("Typo in 'helo'.")

        result = await evaluate_answer(card, "helo", llm)

        assert result.is_correct is False
        assert len(result.highlighted_chars) == len("helo")
        chars = [h.char for h in result.highlighted_chars]
        assert chars == list("helo")

    async def test_correct_value_is_stripped_translation(self) -> None:
        """correct_value returned is stripped card.translation."""
        from lingosips.core.practice import evaluate_answer

        card = _make_card(translation="  hello  ")
        llm = _make_llm()

        result = await evaluate_answer(card, "hello", llm)

        assert result.correct_value == "hello"
