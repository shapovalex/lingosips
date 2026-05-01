"""Tests for api/models.py — written BEFORE implementation (TDD).

Covers GET /models/status endpoint and SSE generator paths.
"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
class TestModelDownloadSSEGenerator:
    """Unit tests for the _model_download_sse internal generator."""

    async def test_yields_complete_immediately_when_model_ready(self, session):
        """When model is ready, yields only the complete event."""
        from lingosips.api.models import _model_download_sse

        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = True
            events = []
            async for event in _model_download_sse(session):
                events.append(event)

        assert len(events) == 1
        assert "event: complete" in events[0]
        assert "Model ready" in events[0]

    async def test_starts_download_when_no_job_exists(self, session):
        """When model is not ready and no job exists, starts a download."""

        from lingosips.api.models import _model_download_sse
        from lingosips.db.models import Job

        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = False

            # start_download creates the job and returns its id
            async def fake_start_download(s):
                job = Job(
                    job_type="model_download",
                    status="complete",
                    progress_done=100,
                    progress_total=100,
                    current_item="Complete",
                )
                s.add(job)
                await s.commit()
                await s.refresh(job)
                return job.id

            mock_mm.start_download = fake_start_download

            events = []
            async for event in _model_download_sse(session):
                events.append(event)

        # Should have yielded a complete event
        assert any("event: complete" in e for e in events)

    async def test_polls_existing_running_job_until_complete(self, session):
        """When a running job exists, polls until status is 'complete'."""

        from lingosips.api.models import _model_download_sse
        from lingosips.db.models import Job

        # Create a job that starts as 'running' then flips to 'complete'
        job = Job(
            job_type="model_download",
            status="running",
            progress_done=50,
            progress_total=100,
            current_item="50% downloaded",
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

        call_count = 0

        # Patch asyncio.sleep to flip the job to complete on second poll
        async def mock_sleep(secs):  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                # Update job status on second sleep
                job.status = "complete"
                job.progress_done = 100
                job.progress_total = 100
                job.current_item = "Complete"
                session.add(job)
                await session.commit()

        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = False
            with patch("lingosips.api.models.asyncio.sleep", side_effect=mock_sleep):
                events = []
                async for event in _model_download_sse(session):
                    events.append(event)
                    if len(events) > 10:  # safety limit
                        break

        assert any("event: progress" in e for e in events)
        assert any("event: complete" in e for e in events)

    async def test_starts_new_download_when_most_recent_job_is_failed(self, session):
        """Stale failed job must not block a new download — only running jobs are attached."""
        from lingosips.api.models import _model_download_sse
        from lingosips.db.models import Job

        # Create a previously-failed job (most recent)
        failed_job = Job(
            job_type="model_download",
            status="failed",
            progress_done=0,
            progress_total=0,
            current_item="Network error",
            error_message="Network error",
        )
        session.add(failed_job)
        await session.commit()
        await session.refresh(failed_job)

        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = False

            async def fake_start_download(s):
                new_job = Job(
                    job_type="model_download",
                    status="complete",
                    progress_done=100,
                    progress_total=100,
                    current_item="Complete",
                )
                s.add(new_job)
                await s.commit()
                await s.refresh(new_job)
                return new_job.id

            mock_mm.start_download = fake_start_download

            with patch("lingosips.api.models.asyncio.sleep"):
                events = []
                async for event in _model_download_sse(session):
                    events.append(event)

        # Must have started a fresh download and emitted complete
        assert any("event: complete" in e for e in events)

    async def test_sse_emits_error_on_poll_timeout(self, session):
        """SSE emits error when job stays in 'running' state beyond _SSE_MAX_POLLS."""
        import lingosips.api.models as models_module
        from lingosips.api.models import _model_download_sse
        from lingosips.db.models import Job

        job = Job(
            job_type="model_download",
            status="running",
            progress_done=10,
            progress_total=100,
            current_item="Downloading...",
        )
        session.add(job)
        # flush (not commit) — rolled back after test; session queries still see it
        await session.flush()
        await session.refresh(job)

        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = False
            # Reduce poll limit to 2 so the timeout triggers quickly
            with patch.object(models_module, "_SSE_MAX_POLLS", 2):
                with patch("lingosips.api.models.asyncio.sleep"):
                    events = []
                    async for event in _model_download_sse(session):
                        events.append(event)

        assert any("event: error" in e and "timed out" in e for e in events)

    async def test_emits_error_when_job_fails(self, session):
        """When a download job fails, emits an error event."""
        from lingosips.api.models import _model_download_sse
        from lingosips.db.models import Job

        job = Job(
            job_type="model_download",
            status="running",
            progress_done=10,
            progress_total=100,
            current_item="Downloading...",
            error_message=None,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

        call_count = 0

        async def mock_sleep(secs):  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                job.status = "failed"
                job.error_message = "Network error"
                session.add(job)
                await session.commit()

        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = False
            with patch("lingosips.api.models.asyncio.sleep", side_effect=mock_sleep):
                events = []
                async for event in _model_download_sse(session):
                    events.append(event)

        assert any("event: error" in e and "Network error" in e for e in events)


@pytest.mark.anyio
class TestModelStatusEndpoint:
    async def test_get_model_status_when_ready(self, client: AsyncClient):
        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = True
            mock_mm.model_filename = "qwen2.5-3b-instruct-q4_k_m.gguf"
            response = await client.get("/models/status")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["downloading"] is False
        assert "model_name" in body

    async def test_get_model_status_when_not_ready(self, client: AsyncClient):
        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = False
            mock_mm.model_filename = "qwen2.5-3b-instruct-q4_k_m.gguf"
            response = await client.get("/models/status")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is False

    async def test_get_model_status_returns_model_name(self, client: AsyncClient):
        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = True
            mock_mm.model_filename = "qwen2.5-3b-instruct-q4_k_m.gguf"
            response = await client.get("/models/status")
        assert response.status_code == 200
        body = response.json()
        assert body["model_name"] == "qwen2.5-3b-instruct-q4_k_m.gguf"

    async def test_download_progress_endpoint_exists(self, client: AsyncClient):
        """GET /models/download/progress must be a registered endpoint."""
        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = True
            mock_mm.model_filename = "qwen2.5-3b-instruct-q4_k_m.gguf"
            response = await client.get("/models/download/progress")
        # When model is ready, SSE immediately emits complete event and closes
        assert response.status_code == 200

    async def test_download_progress_emits_complete_when_model_ready(self, client: AsyncClient):
        """SSE endpoint emits 'complete' event immediately when model is already ready."""
        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = True
            response = await client.get("/models/download/progress")
        assert response.status_code == 200
        assert "event: complete" in response.text
        assert "Model ready" in response.text

    async def test_model_status_with_active_download_job(self, client: AsyncClient, session):
        """GET /models/status shows downloading=True when a running job exists."""
        from lingosips.db.models import Job

        # Create a running download job
        job = Job(
            job_type="model_download",
            status="running",
            progress_done=512,
            progress_total=1024,
            current_item="50% downloaded",
        )
        session.add(job)
        # flush (not commit) — visible within this session, rolled back after test
        await session.flush()

        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = False
            mock_mm.model_filename = "qwen2.5-3b-instruct-q4_k_m.gguf"
            response = await client.get("/models/status")

        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is False
        assert body["downloading"] is True
        assert body["progress_pct"] == 50.0

    async def test_model_status_progress_pct_clamped_to_100(self, client: AsyncClient, session):
        """progress_pct must never exceed 100 even if done > total (race condition)."""
        from lingosips.db.models import Job

        job = Job(
            job_type="model_download",
            status="running",
            progress_done=1100,  # more than total — race condition
            progress_total=1000,
            current_item="Finalizing...",
        )
        session.add(job)
        # flush (not commit) — visible within this session, rolled back after test
        await session.flush()

        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = False
            mock_mm.model_filename = "qwen2.5-3b-instruct-q4_k_m.gguf"
            response = await client.get("/models/status")

        assert response.status_code == 200
        assert response.json()["progress_pct"] == 100.0
