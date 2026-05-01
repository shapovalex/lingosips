"""FastAPI application factory for lingosips."""

import os
import re
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from lingosips.core.logging import CREDENTIAL_PATTERNS as _SCRUB_PATTERNS

STATIC_DIR = Path(__file__).parent.parent / "static"

logger = structlog.get_logger(__name__)

# ── Credential scrubbing helpers ──────────────────────────────────────────────
# These ensure credential values are never exposed in HTTP error responses.
# _SCRUB_PATTERNS is imported from core/logging.py (single source of truth).


def _scrub_string(s: str) -> str:
    """Replace credential patterns in a string with [REDACTED]."""
    for pattern in _SCRUB_PATTERNS:
        s = pattern.sub("[REDACTED]", s)
    return s


def _scrub_detail(detail: str | dict | None) -> str | dict:
    """Scrub credential values from an HTTPException detail before returning it.

    Handles str, dict (recursively), and None.  Returns an empty string for
    None so the caller's RFC 7807 envelope is used instead of an empty dict.
    """
    if isinstance(detail, str):
        return _scrub_string(detail)
    if isinstance(detail, dict):
        result: dict = {}
        for k, v in detail.items():
            if isinstance(v, (str, dict)):
                result[k] = _scrub_detail(v)
            else:
                result[k] = v
        return result
    # None or any other unexpected type → empty string so the caller builds
    # a proper RFC 7807 envelope rather than returning an empty/invalid body.
    return ""


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """App lifespan handler — startup logic before yield, shutdown after."""
    if os.environ.get("LINGOSIPS_ENV") != "test":
        _schedule_browser_open()
    yield
    # Shutdown logic goes here (if needed in future stories)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from lingosips.api.cards import router as cards_router
    from lingosips.api.decks import router as decks_router
    from lingosips.api.imports import router as imports_router
    from lingosips.api.models import router as models_router
    from lingosips.api.practice import router as practice_router
    from lingosips.api.services import router as services_router
    from lingosips.api.settings import router as settings_router

    application = FastAPI(
        title="lingosips",
        description="Local-first vocabulary learning with FSRS spaced repetition",
        version="0.1.0",
        lifespan=_lifespan,
    )

    # SPA routes that share a path prefix with an API route.
    # When a browser GETs these with Accept: text/html, serve index.html so
    # TanStack Router handles the client-side route instead of the API returning JSON.
    # API fetch calls from client.ts always send Accept: application/json, so they
    # bypass this handler and continue to the router normally.
    _spa_routes_exact = {"/settings", "/practice", "/import", "/progress", "/decks"}
    # Pattern routes: card and deck detail pages share path prefixes with API routes.
    # /cards/{id} → TanStack Router CardDetail (conflicts with GET /cards/{card_id}).
    _spa_route_patterns = [
        re.compile(r"^/cards/\d+$"),
    ]

    @application.middleware("http")
    async def spa_fallback_middleware(request: Request, call_next: Callable[..., Any]) -> Any:
        """Serve index.html for browser navigations to SPA routes that overlap with API paths."""
        index_html = STATIC_DIR / "index.html"
        accept = request.headers.get("accept", "")
        path = request.url.path
        is_spa_route = path in _spa_routes_exact or any(
            p.match(path) for p in _spa_route_patterns
        )
        if (
            request.method == "GET"
            and is_spa_route
            and "text/html" in accept
            and index_html.exists()
        ):
            response = FileResponse(str(index_html))
            # Prevent the browser from caching the HTML response at API-shared
            # paths (e.g. /settings).  Without this the browser serves the
            # cached HTML for subsequent React fetch("/settings") calls that
            # send Accept: application/json, causing JSON-parse failures.
            response.headers["Cache-Control"] = "no-store"
            return response
        return await call_next(request)

    # RFC 7807 Problem Details exception handler — all errors return JSON, never HTML.
    # Credential values in exc.detail are scrubbed before the response is sent (AC3).
    # SPA fallback: for browser 404s (Accept: text/html), serve index.html so
    # TanStack Router can handle client-side routes like /settings, /practice, etc.
    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse | FileResponse:
        if exc.status_code == 404:
            index_html = STATIC_DIR / "index.html"
            accept = request.headers.get("accept", "")
            if index_html.exists() and "text/html" in accept:
                return FileResponse(str(index_html))
        scrubbed = _scrub_detail(exc.detail)
        if isinstance(scrubbed, dict):
            body = scrubbed
        else:
            body = {
                "type": f"/errors/{exc.status_code}",
                "title": scrubbed,
                "status": exc.status_code,
            }
        return JSONResponse(
            status_code=exc.status_code,
            content=body,
            headers={"Content-Type": "application/problem+json"},
        )

    # RFC 7807 handler for Pydantic validation errors (422 Unprocessable Entity).
    # FastAPI's built-in 422 handler returns a non-RFC-7807 body; this replaces it.
    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return RFC 7807 Problem Details for request validation failures."""
        errors = [
            {
                "field": ".".join(str(loc) for loc in e["loc"]),
                "message": e["msg"],
                "type": e["type"],
            }
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "type": "/errors/validation",
                "title": "Validation error",
                "status": 422,
                "errors": errors,
            },
            headers={"Content-Type": "application/problem+json"},
        )

    # Generic 500 handler — catches all unhandled exceptions.
    # NEVER exposes the exception message, repr, or traceback to the caller (AC3).
    # Logs only the exception class name — credential values may be in str(exc).
    @application.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", exc_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "type": "/errors/internal",
                "title": "Internal server error",
                "status": 500,
            },
            headers={"Content-Type": "application/problem+json"},
        )

    # Health endpoint (AC: 1, 5)
    @application.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    # Domain routers — register after health, before static mount
    # Registration order: health → settings → models → cards → practice → services → decks → static
    application.include_router(settings_router, prefix="/settings", tags=["settings"])
    application.include_router(models_router, prefix="/models", tags=["models"])
    application.include_router(cards_router, prefix="/cards", tags=["cards"])
    application.include_router(practice_router, prefix="/practice", tags=["practice"])
    application.include_router(services_router, prefix="/services", tags=["services"])
    application.include_router(decks_router, prefix="/decks", tags=["decks"])
    application.include_router(imports_router)

    # Mount static files for production (only when static dir has compiled frontend content)
    if STATIC_DIR.exists() and any(STATIC_DIR.iterdir()):
        application.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return application


def _schedule_browser_open() -> None:
    """Non-blocking browser open scheduled as fire-and-forget task.

    Must only be called from within an async context (e.g. the lifespan handler)
    where a running event loop already exists. Uses get_running_loop() rather than
    the deprecated get_event_loop() to avoid DeprecationWarning in Python 3.10+.
    """
    import asyncio
    import webbrowser

    async def _open() -> None:
        await asyncio.sleep(0.5)
        webbrowser.open("http://localhost:7842")

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_open())
    except RuntimeError:
        pass


app = create_app()
