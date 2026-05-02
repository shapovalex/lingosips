"""Whisper model lifecycle manager — tracks download for faster-whisper.

Pattern mirrors services/models/manager.py. Uses the same Job table for
progress tracking so GET /models/download/progress SSE works for both models.
"""

import asyncio
import threading
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from lingosips.db.models import Job

logger = structlog.get_logger(__name__)

WHISPER_MODEL_SIZE = "tiny"  # fastest; adequate for pronunciation evaluation
MODELS_DIR = Path.home() / ".lingosips" / "models"
WHISPER_MODEL_DIR = MODELS_DIR / f"whisper-{WHISPER_MODEL_SIZE}"


class WhisperModelManager:
    """Manages faster-whisper model download and readiness checks.

    Mirrors ModelManager pattern. Uses Job DB model for progress tracking.
    """

    def __init__(self, model_dir: Path = WHISPER_MODEL_DIR) -> None:
        self._model_dir = model_dir
        self._downloading = False
        self._download_lock = asyncio.Lock()

    def is_ready(self) -> bool:
        """Return True if the whisper model directory exists and is non-empty."""
        return self._model_dir.exists() and any(self._model_dir.iterdir())

    def get_model_dir(self) -> Path:
        """Return the expected model directory path."""
        return self._model_dir

    async def start_download(self, session: AsyncSession) -> int:
        """Create a Job record and start faster-whisper model download.

        CRITICAL: Job persisted to DB BEFORE download starts.
        Returns job_id for SSE progress tracking.
        """
        async with self._download_lock:
            if self._downloading:
                result = await session.execute(
                    select(Job)
                    .where(Job.job_type == "model_download", Job.status == "running")
                    .limit(1)
                )
                existing = result.scalars().first()
                if existing and existing.id:
                    return existing.id

            job = Job(
                job_type="model_download",
                status="running",
                progress_done=0,
                progress_total=100,
                current_item=f"Downloading faster-whisper-{WHISPER_MODEL_SIZE}",
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_id = job.id
            if job_id is None:
                raise RuntimeError("Job ID was not assigned after DB commit")

            self._downloading = True
            self._model_dir.mkdir(parents=True, exist_ok=True)

            from lingosips.db.session import AsyncSessionLocal

            thread = threading.Thread(
                target=self._download_sync,
                args=(job_id, AsyncSessionLocal),
                daemon=True,
            )
            thread.start()
            logger.info("whisper.download_started", job_id=job_id, model=WHISPER_MODEL_SIZE)
            return job_id

    def _download_sync(self, job_id: int, session_factory: object) -> None:  # pragma: no cover
        """Download faster-whisper model using faster_whisper.download_model().

        Runs in background thread. Updates Job progress to 50% during download,
        100% on complete.
        """
        import asyncio

        from faster_whisper import download_model

        async def _update_job(done: int, total: int, item: str, status: str = "running") -> None:
            async with session_factory() as s:
                result = await s.execute(select(Job).where(Job.id == job_id))
                job = result.scalars().first()
                if job:
                    job.progress_done = done
                    job.progress_total = total
                    job.current_item = item
                    job.status = status
                    s.add(job)
                    await s.commit()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_update_job(10, 100, "Downloading model weights…"))
            download_model(WHISPER_MODEL_SIZE, output_dir=str(self._model_dir))
            loop.run_until_complete(_update_job(100, 100, "Complete", "complete"))
            logger.info("whisper.download_complete", job_id=job_id)
        except Exception as exc:
            loop.run_until_complete(_update_job(0, 100, f"Failed: {exc!s}", "failed"))
            logger.error("whisper.download_failed", job_id=job_id, error=str(exc))
        finally:
            self._downloading = False
            loop.close()
