"""Model lifecycle manager for local AI models.

This is the ONLY place that knows about model file locations.
No other module constructs ~/.lingosips/models/ paths directly.
"""

import asyncio
import threading
from pathlib import Path

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from lingosips.db.models import Job

logger = structlog.get_logger(__name__)

QWEN_MODEL_FILENAME = "qwen2.5-3b-instruct-q4_k_m.gguf"
QWEN_MODEL_URL = (
    "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF"
    "/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
)
MODELS_DIR = Path.home() / ".lingosips" / "models"


class ModelManager:
    """Owns all model download, path discovery, and lifecycle for local AI models.

    This is the ONLY place that knows about model file locations.
    No other module constructs ~/.lingosips/models/ paths directly.
    """

    def __init__(
        self,
        models_dir: Path = MODELS_DIR,
        model_filename: str = QWEN_MODEL_FILENAME,
    ) -> None:
        self._models_dir = models_dir
        self._model_filename = model_filename
        self._downloading = False  # guard: prevent concurrent downloads
        self._download_lock = asyncio.Lock()  # prevent TOCTOU race in start_download

    def is_ready(self) -> bool:
        """Return True if the Qwen model file exists and is non-zero size."""
        path = self.get_model_path()
        return path.exists() and path.stat().st_size > 0

    def get_model_path(self) -> Path:
        """Return the expected model path (file may or may not exist)."""
        return self._models_dir / self._model_filename

    @property
    def model_filename(self) -> str:
        """Return the model filename (public accessor — avoids private attribute access)."""
        return self._model_filename

    async def start_download(self, session: AsyncSession) -> int:
        """Create a Job record and start the download in a background thread.

        CRITICAL: Job is persisted to DB BEFORE download work starts.
        Returns the job_id so callers can track progress.
        The asyncio.Lock prevents concurrent coroutines from creating duplicate jobs.
        """
        async with self._download_lock:
            if self._downloading:
                # Find existing running job and return its ID
                result = await session.execute(
                    select(Job)
                    .where(
                        Job.job_type == "model_download",
                        Job.status == "running",
                    )
                    .limit(1)
                )
                existing = result.scalars().first()
                if existing and existing.id:
                    return existing.id

            # Persist job FIRST — data never lost on restart
            job = Job(
                job_type="model_download",
                status="running",
                progress_done=0,
                progress_total=0,
                current_item=f"Downloading {self._model_filename}",
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_id = job.id
            if job_id is None:
                raise RuntimeError("Job ID was not assigned after DB commit")

            self._downloading = True
            self._models_dir.mkdir(parents=True, exist_ok=True)

            # Import here to avoid circular at module level
            from lingosips.db.session import AsyncSessionLocal

            # Fire-and-forget in background thread
            thread = threading.Thread(
                target=self._download_sync,
                args=(QWEN_MODEL_URL, self.get_model_path(), job_id, AsyncSessionLocal),
                daemon=True,
            )
            thread.start()
            logger.info("model.download_started", job_id=job_id, filename=self._model_filename)
            return job_id

    def _download_sync(  # pragma: no cover
        self, url: str, dest: Path, job_id: int, session_factory: object
    ) -> None:
        """Blocking download — runs in background thread. Updates Job progress."""

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
            with httpx.Client(timeout=600.0, follow_redirects=True) as client:
                with client.stream("GET", url) as response:
                    total = int(response.headers.get("content-length", 0))
                    done = 0
                    last_pct = -1
                    with open(dest, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=1024 * 1024):  # 1MB chunks
                            f.write(chunk)
                            done += len(chunk)
                            pct = int(done / total * 100) if total else 0
                            if pct != last_pct:
                                loop.run_until_complete(
                                    _update_job(done, total, f"{pct}% downloaded")
                                )
                                last_pct = pct
            loop.run_until_complete(_update_job(total, total, "Complete", "complete"))
            logger.info("model.download_complete", job_id=job_id)
        except Exception as exc:
            loop.run_until_complete(_update_job(0, 0, f"Failed: {exc!s}", "failed"))
            logger.error("model.download_failed", job_id=job_id, error=str(exc))
            if dest.exists():
                try:
                    dest.unlink()  # clean up partial file
                except OSError as unlink_err:
                    logger.error("model.cleanup_failed", job_id=job_id, error=str(unlink_err))
        finally:
            self._downloading = False
            loop.close()
