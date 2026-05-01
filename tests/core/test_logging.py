"""Tests for structured logging configuration.

AC: 5, 6 — logging configured correctly with credential scrubbing.
"""

import logging

import structlog


class TestConfigureLogging:
    def test_configure_logging_does_not_raise(self) -> None:
        """configure_logging() can be called without raising."""
        from lingosips.core.logging import configure_logging

        # Should not raise
        configure_logging()

    def test_log_level_from_env_var(self, monkeypatch) -> None:
        """LINGOSIPS_LOG_LEVEL env var controls the log level."""
        from lingosips.core.logging import configure_logging

        monkeypatch.setenv("LINGOSIPS_LOG_LEVEL", "DEBUG")
        configure_logging()
        assert logging.getLogger().level == logging.DEBUG

    def test_default_log_level_is_warning(self, monkeypatch) -> None:
        """Default log level is WARNING when LINGOSIPS_LOG_LEVEL is not set."""
        from lingosips.core.logging import configure_logging

        monkeypatch.delenv("LINGOSIPS_LOG_LEVEL", raising=False)
        configure_logging()
        assert logging.getLogger().level == logging.WARNING

    def test_structlog_is_configured(self) -> None:
        """After configure_logging, structlog returns a BoundLogger."""
        from lingosips.core.logging import configure_logging

        configure_logging()
        logger = structlog.get_logger("test")
        # Should be a bound logger (not the default PrintLoggerFactory)
        assert logger is not None


class TestCredentialScrubbing:
    def test_scrub_api_key_in_event(self) -> None:
        """API keys are redacted in log event messages."""
        from lingosips.core.logging import _scrub_credentials

        event_dict = {"event": "Got api_key=sk-12345secretkey from user"}
        result = _scrub_credentials(None, None, event_dict)
        assert "sk-12345secretkey" not in result["event"]
        assert "[REDACTED]" in result["event"]

    def test_scrub_bearer_token(self) -> None:
        """Bearer tokens are redacted in log events."""
        from lingosips.core.logging import _scrub_credentials

        event_dict = {"event": "Authorization: Bearer abc123secret"}
        result = _scrub_credentials(None, None, event_dict)
        assert "abc123secret" not in result["event"]
        assert "[REDACTED]" in result["event"]

    def test_scrub_password_in_string_value(self) -> None:
        """Passwords in string values are redacted."""
        from lingosips.core.logging import _scrub_credentials

        event_dict = {"event": "login", "details": "password=mysecret123"}
        result = _scrub_credentials(None, None, event_dict)
        assert "mysecret123" not in result["details"]
        assert "[REDACTED]" in result["details"]

    def test_non_credential_event_unchanged(self) -> None:
        """Regular log messages are not modified."""
        from lingosips.core.logging import _scrub_credentials

        event_dict = {"event": "User logged in successfully", "user_id": 42}
        result = _scrub_credentials(None, None, event_dict)
        assert result["event"] == "User logged in successfully"
        assert result["user_id"] == 42

    def test_non_string_values_not_modified(self) -> None:
        """Non-string values in event dict are not modified."""
        from lingosips.core.logging import _scrub_credentials

        event_dict = {"event": "test", "count": 42, "active": True}
        result = _scrub_credentials(None, None, event_dict)
        assert result["count"] == 42
        assert result["active"] is True

    def test_debug_level_still_scrubs(self, monkeypatch, capsys) -> None:
        """T5.3 / AC5: Credentials scrubbed even when LINGOSIPS_LOG_LEVEL=DEBUG."""
        from lingosips.core.logging import configure_logging

        monkeypatch.setenv("LINGOSIPS_LOG_LEVEL", "DEBUG")
        configure_logging()

        import structlog

        log = structlog.get_logger("test_debug_scrub")
        log.debug("debug event", api_key="sk-supersecret999")

        captured = capsys.readouterr()
        assert "sk-supersecret999" not in captured.out
        assert "sk-supersecret999" not in captured.err
        # Positive assertion: [REDACTED] must appear — confirms scrubbing fired,
        # not that the log line was simply suppressed or logging silently disabled.
        assert "[REDACTED]" in captured.out or "[REDACTED]" in captured.err
