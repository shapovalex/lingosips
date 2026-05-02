"""Import pipeline API — preview and job management.

LAYER RULE: All parsing logic lives in core/imports.py.
This router only validates inputs, delegates, and returns responses.
"""

import asyncio
import json

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlmodel.ext.asyncio.session import AsyncSession

from lingosips.core import imports as core_imports
from lingosips.db.models import Job
from lingosips.db.session import get_session

router = APIRouter(prefix="/import", tags=["import"])
logger = structlog.get_logger(__name__)


# ── Response models ───────────────────────────────────────────────────────────


class CardPreviewItemResponse(BaseModel):
    target_word: str
    translation: str | None
    example_sentence: str | None
    has_audio: bool
    fields_missing: list[str]
    selected: bool


class ImportPreviewResponse(BaseModel):
    source_type: str
    total_cards: int
    fields_present: list[str]
    fields_missing_summary: dict[str, int]
    cards: list[CardPreviewItemResponse]
    # Optional fields — populated by lingosips source
    deck_name: str | None = None
    target_language: str | None = None


# ── Preview endpoints ─────────────────────────────────────────────────────────


@router.post("/preview/anki", response_model=ImportPreviewResponse)
async def preview_anki(file: UploadFile = File(...)) -> ImportPreviewResponse:
    """Parse uploaded .apkg file and return preview (no cards created)."""
    file_bytes = await file.read()
    try:
        preview = core_imports.parse_apkg(file_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "/errors/invalid-import-file",
                "title": str(exc),
                "status": 422,
            },
        )
    return ImportPreviewResponse(
        source_type=preview.source_type,
        total_cards=preview.total_cards,
        fields_present=preview.fields_present,
        fields_missing_summary=preview.fields_missing_summary,
        cards=[CardPreviewItemResponse(**vars(c)) for c in preview.cards],
    )


class TextPreviewRequest(BaseModel):
    text: str
    format: str = "auto"  # "auto" | "plain" | "tsv"

    @field_validator("format")
    @classmethod
    def valid_format(cls, v: str) -> str:
        if v not in ("auto", "plain", "tsv"):
            raise ValueError("format must be 'auto', 'plain', or 'tsv'")
        return v


@router.post("/preview/text", response_model=ImportPreviewResponse)
async def preview_text(request: TextPreviewRequest) -> ImportPreviewResponse:
    """Parse plain text or TSV and return preview (no cards created)."""
    preview = core_imports.parse_text_import(request.text, format=request.format)
    return ImportPreviewResponse(
        source_type=preview.source_type,
        total_cards=preview.total_cards,
        fields_present=preview.fields_present,
        fields_missing_summary=preview.fields_missing_summary,
        cards=[CardPreviewItemResponse(**vars(c)) for c in preview.cards],
    )


class UrlPreviewRequest(BaseModel):
    url: str


@router.post("/preview/url", response_model=ImportPreviewResponse)
async def preview_url(request: UrlPreviewRequest) -> ImportPreviewResponse:
    """Fetch URL and return word candidates as preview (no cards created)."""
    try:
        preview = await core_imports.parse_url_import(request.url)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "/errors/url-fetch-failed",
                "title": str(exc),
                "status": 422,
            },
        )
    return ImportPreviewResponse(
        source_type=preview.source_type,
        total_cards=preview.total_cards,
        fields_present=preview.fields_present,
        fields_missing_summary=preview.fields_missing_summary,
        cards=[CardPreviewItemResponse(**vars(c)) for c in preview.cards],
    )


# ── Import start endpoint ─────────────────────────────────────────────────────


class ImportStartRequest(BaseModel):
    source_type: str
    cards: list[core_imports.CardImportItem]
    target_language: str
    deck_id: int | None = None
    enrich: bool = True

    @field_validator("cards")
    @classmethod
    def cards_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("cards must not be empty")
        return v


class ImportStartResponse(BaseModel):
    job_id: int
    card_count: int


@router.post("/start", response_model=ImportStartResponse)
async def start_import(
    request: ImportStartRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> ImportStartResponse:
    """Create cards + job, then launch enrichment as a background task."""
    from lingosips.db.session import engine  # noqa: PLC0415 — import engine URL for bg task
    from lingosips.services.credentials import (  # noqa: PLC0415
        OPENROUTER_API_KEY,
        OPENROUTER_MODEL,
        get_credential,
    )

    job_id, card_ids = await core_imports.create_cards_and_job(
        cards_data=request.cards,
        target_language=request.target_language,
        deck_id=request.deck_id,
        session=session,
    )
    if request.enrich:
        db_url = str(engine.url)
        llm_api_key = get_credential(OPENROUTER_API_KEY)
        llm_model = get_credential(OPENROUTER_MODEL)
        background_tasks.add_task(
            core_imports.run_enrichment,
            job_id=job_id,
            card_ids=card_ids,
            db_engine_url=db_url,
            llm_api_key=llm_api_key,
            llm_model=llm_model,
        )
    logger.info("import.started", job_id=job_id, card_count=len(card_ids))
    return ImportStartResponse(job_id=job_id, card_count=len(card_ids))


# ── .lingosips import endpoints ──────────────────────────────────────────────


class LingosipsImportStartResponse(BaseModel):
    deck_id: int
    card_count: int


@router.post("/preview/lingosips", response_model=ImportPreviewResponse)
async def preview_lingosips(file: UploadFile = File(...)) -> ImportPreviewResponse:
    """Parse uploaded .lingosips file and return preview (no cards created)."""
    file_bytes = await file.read()
    try:
        preview = core_imports.parse_lingosips_file(file_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "/errors/invalid-lingosips-file",
                "title": "Invalid .lingosips file",
                "status": 422,
                "detail": str(exc),
            },
        )
    return ImportPreviewResponse(
        source_type="lingosips",
        total_cards=preview.total_cards,
        fields_present=["target_word", "translation", "forms", "example_sentences"],
        fields_missing_summary={},  # lingosips files are already enriched
        deck_name=preview.deck_name,
        target_language=preview.target_language,
        cards=[
            CardPreviewItemResponse(
                target_word=c.target_word,
                translation=c.translation,
                example_sentence=None,
                has_audio=c.audio_file is not None,
                fields_missing=[],
                selected=True,
            )
            for c in preview.sample_cards
        ],
    )


@router.post("/start/lingosips", response_model=LingosipsImportStartResponse, status_code=201)
async def start_lingosips_import(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> LingosipsImportStartResponse:
    """Import a .lingosips file: create deck + all cards synchronously (no enrichment)."""
    file_bytes = await file.read()
    try:
        deck_id, card_count = await core_imports.import_lingosips_deck(file_bytes, session)
    except ValueError as exc:
        msg = str(exc)
        status = 409 if "conflict" in msg.lower() else 422
        error_type = (
            "/errors/deck-name-conflict" if status == 409 else "/errors/invalid-lingosips-file"
        )
        raise HTTPException(
            status_code=status,
            detail={
                "type": error_type,
                "title": "Deck name conflict" if status == 409 else "Invalid .lingosips file",
                "status": status,
                "detail": msg,
            },
        )
    logger.info("lingosips.import.complete", deck_id=deck_id, card_count=card_count)
    return LingosipsImportStartResponse(deck_id=deck_id, card_count=card_count)


# ── Progress SSE endpoint ─────────────────────────────────────────────────────


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@router.get("/{job_id}/progress")
async def import_progress(
    job_id: int,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """SSE stream of enrichment progress. Polls job table every 500ms.

    SSE envelope identical to other channels:
      event: progress\\ndata: {"done": N, "total": M, "current_item": "..."}\\n\\n
      event: complete\\ndata: {"enriched": N, "unresolved": M}\\n\\n
      event: error\\ndata: {"message": "..."}\\n\\n
    """
    # Validate job exists before starting the stream
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/job-not-found",
                "title": f"Job {job_id} not found",
                "status": 404,
            },
        )

    # Capture terminal state before closing the session
    initial_status = job.status
    initial_progress_total = job.progress_total
    initial_error_message = job.error_message

    # Close the request session before streaming (SSE uses its own sessions)
    await session.close()

    # If job is already in a terminal state, return single-shot SSE without polling
    if initial_status in ("complete", "failed"):

        async def terminal_event_generator():
            if initial_status == "complete":
                unresolved = 0
                if initial_error_message and initial_error_message.startswith("unresolved:"):
                    try:
                        unresolved = int(initial_error_message.split(":")[1])
                    except (IndexError, ValueError):
                        pass
                enriched = initial_progress_total - unresolved
                yield _sse_event("complete", {"enriched": enriched, "unresolved": unresolved})
            else:
                yield _sse_event("error", {"message": initial_error_message or "Import failed"})

        return StreamingResponse(terminal_event_generator(), media_type="text/event-stream")

    async def event_generator():
        from sqlalchemy.ext.asyncio import (  # noqa: PLC0415
            AsyncSession as SAAsyncSession,
        )
        from sqlalchemy.orm import sessionmaker as sa_sessionmaker  # noqa: PLC0415

        from lingosips.db.session import engine as db_engine  # noqa: PLC0415

        async_session = sa_sessionmaker(db_engine, class_=SAAsyncSession, expire_on_commit=False)
        try:
            while True:
                async with async_session() as poll_session:
                    current_job = await poll_session.get(Job, job_id)
                    if not current_job:
                        yield _sse_event("error", {"message": f"Job {job_id} disappeared"})
                        return

                    if current_job.status == "complete":
                        # Parse unresolved count from error_message encoding
                        unresolved = 0
                        if current_job.error_message and current_job.error_message.startswith(
                            "unresolved:"
                        ):
                            try:
                                unresolved = int(current_job.error_message.split(":")[1])
                            except (IndexError, ValueError):
                                pass
                        enriched = current_job.progress_total - unresolved
                        yield _sse_event(
                            "complete", {"enriched": enriched, "unresolved": unresolved}
                        )
                        return
                    elif current_job.status == "failed":
                        yield _sse_event(
                            "error",
                            {"message": current_job.error_message or "Import failed"},
                        )
                        return
                    else:
                        yield _sse_event(
                            "progress",
                            {
                                "done": current_job.progress_done,
                                "total": current_job.progress_total,
                                "current_item": current_job.current_item or "processing...",
                            },
                        )
                await asyncio.sleep(0.5)  # poll every 500ms
        except asyncio.CancelledError:
            pass  # client disconnected — enrichment continues in background

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Job status endpoint ───────────────────────────────────────────────────────


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    progress_done: int
    progress_total: int
    current_item: str | None
    error_message: str | None


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: int,
    session: AsyncSession = Depends(get_session),
) -> JobStatusResponse:
    """Get current job status (for reconnect after page reload)."""
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/job-not-found",
                "title": f"Job {job_id} not found",
                "status": 404,
            },
        )
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress_done=job.progress_done,
        progress_total=job.progress_total,
        current_item=job.current_item,
        error_message=job.error_message,
    )
