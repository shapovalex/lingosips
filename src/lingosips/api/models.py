"""API endpoints for model status and download progress.

Provides:
- GET /models/status    — current status of the local Qwen model
- GET /models/download/progress — SSE stream for download progress
"""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from lingosips.db.models import Job
from lingosips.db.session import get_session
from lingosips.services.registry import _model_manager  # direct access to singleton

router = APIRouter()

# Hard stop for the SSE polling loop: ~1 hour at 500 ms per iteration.
# Prevents an infinite hang if the download thread crashes without updating the DB.
_SSE_MAX_POLLS = 7200


class ModelStatusResponse(BaseModel):
    """Response model for GET /models/status (T6.1)."""

    model_name: str
    ready: bool
    downloading: bool
    progress_pct: float | None = None


async def _model_download_sse(session: AsyncSession) -> AsyncIterator[str]:
    """SSE generator for model download progress."""
    if _model_manager.is_ready():
        yield f"event: complete\ndata: {json.dumps({'message': 'Model ready'})}\n\n"
        return

    # Only attach to an actively running job — stale failed/complete jobs are ignored
    # so that a new download is started when the client reconnects after a failure.
    result = await session.execute(
        select(Job)
        .where(Job.job_type == "model_download", Job.status == "running")
        .order_by(Job.created_at.desc())  # type: ignore[attr-defined]
        .limit(1)
    )
    job = result.scalars().first()

    if job is None:
        # No active download — start one
        job_id = await _model_manager.start_download(session)
    else:
        job_id = job.id

    # Poll DB until complete, failed, or timeout
    for _ in range(_SSE_MAX_POLLS):
        await asyncio.sleep(0.5)  # poll every 500 ms

        result = await session.execute(select(Job).where(Job.id == job_id))
        current_job = result.scalars().first()

        if current_job is None:
            yield f"event: error\ndata: {json.dumps({'message': 'Job not found'})}\n\n"
            return

        if current_job.status == "complete":
            progress_data = json.dumps(
                {
                    "done": current_job.progress_total,
                    "total": current_job.progress_total,
                    "current_item": "Complete",
                }
            )
            yield f"event: progress\ndata: {progress_data}\n\n"
            yield f"event: complete\ndata: {json.dumps({'message': 'Model ready'})}\n\n"
            return

        if current_job.status == "failed":
            error_data = json.dumps(
                {"message": current_job.error_message or "Download failed"}
            )
            yield f"event: error\ndata: {error_data}\n\n"
            return

        # Still running — emit progress
        progress_data = json.dumps(
            {
                "done": current_job.progress_done,
                "total": current_job.progress_total,
                "current_item": current_job.current_item,
            }
        )
        yield f"event: progress\ndata: {progress_data}\n\n"

    # Timeout — download thread may have crashed without updating DB
    timeout_msg = json.dumps({"message": "Download timed out — check server logs"})
    yield f"event: error\ndata: {timeout_msg}\n\n"


@router.get("/status")
async def get_model_status(session: AsyncSession = Depends(get_session)) -> ModelStatusResponse:
    """Return current status of the local Qwen model."""
    ready = _model_manager.is_ready()
    result = await session.execute(
        select(Job)
        .where(Job.job_type == "model_download", Job.status == "running")
        .limit(1)
    )
    active_job = result.scalars().first()
    progress_pct = None
    if active_job and active_job.progress_total > 0:
        raw_pct = active_job.progress_done / active_job.progress_total * 100
        progress_pct = min(round(raw_pct, 1), 100.0)  # clamp — never exceed 100
    return ModelStatusResponse(
        model_name=_model_manager.model_filename,
        ready=ready,
        downloading=active_job is not None,
        progress_pct=progress_pct,
    )


@router.get("/download/progress")
async def download_progress(session: AsyncSession = Depends(get_session)) -> StreamingResponse:
    """SSE stream for model download progress.

    Event types emitted: progress | complete | error
    progress data: {"done": int, "total": int, "current_item": str}
    complete data: {"message": "Model ready"}
    error data: {"message": str}
    """
    return StreamingResponse(
        _model_download_sse(session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
