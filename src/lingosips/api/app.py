"""FastAPI application factory for lingosips."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """App lifespan handler — startup logic before yield, shutdown after."""
    if os.environ.get("LINGOSIPS_ENV") != "test":
        _schedule_browser_open()
    yield
    # Shutdown logic goes here (if needed in future stories)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="lingosips",
        description="Local-first vocabulary learning with FSRS spaced repetition",
        version="0.1.0",
        lifespan=_lifespan,
    )

    # RFC 7807 Problem Details exception handler — all errors return JSON, never HTML
    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            body = exc.detail
        else:
            body = {
                "type": f"/errors/{exc.status_code}",
                "title": str(exc.detail),
                "status": exc.status_code,
            }
        return JSONResponse(
            status_code=exc.status_code,
            content=body,
            headers={"Content-Type": "application/problem+json"},
        )

    # Health endpoint (AC: 1, 5)
    @application.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

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
