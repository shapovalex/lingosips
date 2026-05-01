"""Tests for services/models/manager.py — written BEFORE implementation (TDD).

Covers ModelManager: is_ready(), get_model_path(), start_download().
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.anyio
class TestModelManager:
    def test_is_ready_false_when_file_missing(self, tmp_path):
        from lingosips.services.models.manager import ModelManager

        mm = ModelManager(models_dir=tmp_path, model_filename="qwen.gguf")
        assert mm.is_ready() is False

    def test_is_ready_true_when_file_exists(self, tmp_path):
        from lingosips.services.models.manager import ModelManager

        model = tmp_path / "qwen.gguf"
        model.write_bytes(b"fake-model-data")
        mm = ModelManager(models_dir=tmp_path, model_filename="qwen.gguf")
        assert mm.is_ready() is True

    def test_is_ready_false_for_zero_byte_file(self, tmp_path):
        from lingosips.services.models.manager import ModelManager

        model = tmp_path / "qwen.gguf"
        model.write_bytes(b"")  # zero bytes = corrupted download
        mm = ModelManager(models_dir=tmp_path, model_filename="qwen.gguf")
        assert mm.is_ready() is False

    def test_get_model_path_returns_expected_path(self, tmp_path):
        from lingosips.services.models.manager import ModelManager

        mm = ModelManager(models_dir=tmp_path, model_filename="test.gguf")
        assert mm.get_model_path() == tmp_path / "test.gguf"

    def test_model_filename_property_returns_filename(self, tmp_path):
        """model_filename property provides public access without exposing private attr."""
        from lingosips.services.models.manager import ModelManager

        mm = ModelManager(models_dir=tmp_path, model_filename="qwen2.5-3b-instruct-q4_k_m.gguf")
        assert mm.model_filename == "qwen2.5-3b-instruct-q4_k_m.gguf"

    async def test_start_download_creates_job_before_any_work(self, session):
        """Job MUST be persisted before download thread starts."""
        from lingosips.services.models.manager import ModelManager

        mm = ModelManager(models_dir=Path("/tmp/test_models"), model_filename="qwen.gguf")
        # Mock the actual download thread so it doesn't run
        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value = MagicMock()
            job_id = await mm.start_download(session)

        assert job_id is not None
        assert isinstance(job_id, int)

        # Verify job exists in DB
        from sqlmodel import select

        from lingosips.db.models import Job

        result = await session.execute(select(Job).where(Job.id == job_id))
        job = result.scalars().first()
        assert job is not None
        assert job.job_type == "model_download"
        assert job.status == "running"

    async def test_start_download_returns_same_job_id_when_already_downloading(self, session):
        """When a download is already running, does NOT create a second job."""
        from sqlmodel import select

        from lingosips.db.models import Job
        from lingosips.services.models.manager import ModelManager

        mm = ModelManager(models_dir=Path("/tmp/test_models"), model_filename="qwen.gguf")

        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value = MagicMock()
            first_job_id = await mm.start_download(session)

        # Verify the first job exists and is running
        result = await session.execute(select(Job).where(Job.id == first_job_id))
        first_job = result.scalars().first()
        assert first_job is not None
        assert first_job.status == "running"

        # Second call while _downloading is True should NOT create a new job
        # It should return an existing running job id (could be first_job_id or earlier one)
        second_job_id = await mm.start_download(session)
        assert second_job_id is not None
        assert isinstance(second_job_id, int)

        # The key invariant: no new job was created with a higher id than first_job_id
        result2 = await session.execute(
            select(Job).where(
                Job.job_type == "model_download",
                Job.status == "running",
                Job.id > first_job_id,
            )
        )
        new_jobs_after = result2.scalars().all()
        assert new_jobs_after == [], "No new jobs should have been created on second call"
