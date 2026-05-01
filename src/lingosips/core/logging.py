"""Structured logging configuration for lingosips.

Uses structlog with a credential-scrubbing processor.
Log level is controlled by the LINGOSIPS_LOG_LEVEL env var (default: WARNING).

IMPORTANT: All OTHER modules must use `import structlog; logger = structlog.get_logger()`
           and NEVER use `import logging` directly.

           This module (core/logging.py) is the ONLY authorized exception: it imports
           stdlib `logging` solely to configure the stdlib→structlog bridge (setting
           root logger level and attaching the structlog formatter). It does NOT use
           `logging` to emit log messages — that is always done through structlog.
"""

import logging
import os
import re
import sys

import structlog

# Patterns for credentials that must never appear in logs or HTTP responses.
# Exported as a public constant so api/app.py can import them for response scrubbing
# rather than maintaining a duplicate list that could drift.
CREDENTIAL_PATTERNS = [
    # Require = or : separator before the value so plain-English phrases like
    # "api_key and model required" are NOT redacted (false-positive guard).
    re.compile(
        r"(api[_-]?key|apikey|password|passwd|secret|token)[\"']?[=:][\"']?\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"sk-[A-Za-z0-9]+"),  # OpenAI/OpenRouter style keys
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
]
_REDACTED = "[REDACTED]"


def _scrub_credentials(logger, method, event_dict):  # noqa: ARG001
    """Structlog processor that removes credentials from log events."""
    # Scrub the event message itself
    event = event_dict.get("event", "")
    if isinstance(event, str):
        for pattern in CREDENTIAL_PATTERNS:
            event = pattern.sub(_REDACTED, event)
        event_dict["event"] = event

    # Scrub all string values in the event dict
    for key, value in event_dict.items():
        if key == "event":
            continue
        if isinstance(value, str):
            for pattern in CREDENTIAL_PATTERNS:
                value = pattern.sub(_REDACTED, value)
            event_dict[key] = value

    return event_dict


def configure_logging() -> None:
    """Configure structlog for the application.

    Must be called once at application startup, before any other module logs.
    """
    log_level_name = os.environ.get("LINGOSIPS_LOG_LEVEL", "WARNING").upper()
    log_level = getattr(logging, log_level_name, logging.WARNING)

    # Configure standard library logging as the backend
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Shared processors for both development and production
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _scrub_credentials,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure structlog formatter for stdlib handlers
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
