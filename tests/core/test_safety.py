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


@pytest.mark.anyio
class TestCheckImage:
    """Tests for check_image() — image safety filter (AC: 2, 3)."""

    def test_valid_png_passes(self) -> None:
        """check_image('image/png', 1024) → (True, None)."""
        from lingosips.core.safety import check_image

        is_safe, reason = check_image("image/png", 1024)
        assert is_safe is True
        assert reason is None

    def test_valid_jpeg_passes(self) -> None:
        """check_image('image/jpeg', 1024) → (True, None)."""
        from lingosips.core.safety import check_image

        is_safe, reason = check_image("image/jpeg", 1024)
        assert is_safe is True
        assert reason is None

    def test_non_image_content_type_rejected(self) -> None:
        """check_image('application/json', 1024) → (False, reason containing 'content-type')."""
        from lingosips.core.safety import check_image

        is_safe, reason = check_image("application/json", 1024)
        assert is_safe is False
        assert reason is not None
        assert "content-type" in reason

    def test_image_exceeding_10mb_rejected(self) -> None:
        """check_image('image/png', 11_000_000) → (False, reason containing '10 MB')."""
        from lingosips.core.safety import check_image

        is_safe, reason = check_image("image/png", 11_000_000)
        assert is_safe is False
        assert reason is not None
        assert "10 MB" in reason

    def test_exactly_10mb_passes(self) -> None:
        """check_image('image/png', 10_485_760) → (True, None) — boundary: exactly 10 MB is OK."""
        from lingosips.core.safety import check_image

        is_safe, reason = check_image("image/png", 10_485_760)
        assert is_safe is True
        assert reason is None

    def test_one_byte_over_10mb_rejected(self) -> None:
        """check_image('image/png', 10_485_761) → (False, ...) — one byte over fails."""
        from lingosips.core.safety import check_image

        is_safe, reason = check_image("image/png", 10_485_761)
        assert is_safe is False
        assert reason is not None


@pytest.mark.anyio
class TestDetectImageContentType:
    """Tests for detect_image_content_type() — magic byte detection."""

    def test_png_magic_bytes_detected(self) -> None:
        """PNG magic bytes → 'image/png'."""
        from lingosips.core.safety import detect_image_content_type

        png_magic = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert detect_image_content_type(png_magic) == "image/png"

    def test_jpeg_magic_bytes_detected(self) -> None:
        """JPEG magic bytes → 'image/jpeg'."""
        from lingosips.core.safety import detect_image_content_type

        jpeg_magic = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        assert detect_image_content_type(jpeg_magic) == "image/jpeg"

    def test_unknown_bytes_returns_none(self) -> None:
        """Unrecognized bytes → None."""
        from lingosips.core.safety import detect_image_content_type

        assert detect_image_content_type(b"not an image at all") is None

    def test_empty_bytes_returns_none(self) -> None:
        """Empty bytes → None."""
        from lingosips.core.safety import detect_image_content_type

        assert detect_image_content_type(b"") is None
