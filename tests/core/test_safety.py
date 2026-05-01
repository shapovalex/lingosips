"""Tests for core/safety.py — content safety filter.

TDD: these tests are written BEFORE implementation to drive core/safety.py.
"""

import pytest


@pytest.mark.anyio
class TestSafetyFilter:
    """Tests for check_text() — the content safety filter."""

    def test_safe_text_returns_true_none(self) -> None:
        """Safe text has no blocked terms → (True, None)."""
        from lingosips.core.safety import check_text

        is_safe, term = check_text("melancholic sadness")
        assert is_safe is True
        assert term is None

    def test_empty_text_is_safe(self) -> None:
        """Empty string is always safe → (True, None)."""
        from lingosips.core.safety import check_text

        is_safe, term = check_text("")
        assert is_safe is True
        assert term is None

    def test_blocked_term_returns_false_and_term(self) -> None:
        """Text containing a blocked term → (False, matched_term)."""
        import lingosips.core.safety as safety_module

        # Temporarily inject a blocked term for testing the mechanism
        original = safety_module.BLOCKED_TERMS[:]
        safety_module.BLOCKED_TERMS.append("test_blocked_word")
        try:
            from lingosips.core.safety import check_text

            is_safe, term = check_text("this text contains test_blocked_word in it")
            assert is_safe is False
            assert term == "test_blocked_word"
        finally:
            safety_module.BLOCKED_TERMS[:] = original

    def test_case_insensitive_match(self) -> None:
        """Matching is case-insensitive — BLOCKED_TERM matches blocked_term."""
        import lingosips.core.safety as safety_module

        original = safety_module.BLOCKED_TERMS[:]
        safety_module.BLOCKED_TERMS.append("badword")
        try:
            from lingosips.core.safety import check_text

            is_safe, term = check_text("Here is BADWORD in uppercase")
            assert is_safe is False
            assert term == "badword"
        finally:
            safety_module.BLOCKED_TERMS[:] = original

    def test_partial_word_match(self) -> None:
        """Blocked term matches as substring — partial word match is sufficient for MVP."""
        import lingosips.core.safety as safety_module

        original = safety_module.BLOCKED_TERMS[:]
        safety_module.BLOCKED_TERMS.append("harm")
        try:
            from lingosips.core.safety import check_text

            # "harm" is a substring of "harmful"
            is_safe, term = check_text("this is harmful content")
            assert is_safe is False
            assert term == "harm"
        finally:
            safety_module.BLOCKED_TERMS[:] = original

    def test_returns_tuple_shape(self) -> None:
        """check_text always returns a 2-tuple (bool, str | None)."""
        from lingosips.core.safety import check_text

        result = check_text("any text")
        assert isinstance(result, tuple)
        assert len(result) == 2
        is_safe, blocked_term = result
        assert isinstance(is_safe, bool)
        assert blocked_term is None or isinstance(blocked_term, str)

    def test_first_blocked_term_wins(self) -> None:
        """When multiple blocked terms match, the first matching term is returned."""
        import lingosips.core.safety as safety_module

        original = safety_module.BLOCKED_TERMS[:]
        safety_module.BLOCKED_TERMS.extend(["alpha", "beta"])
        try:
            from lingosips.core.safety import check_text

            is_safe, term = check_text("alpha and beta are both blocked")
            assert is_safe is False
            assert term == "alpha"
        finally:
            safety_module.BLOCKED_TERMS[:] = original
