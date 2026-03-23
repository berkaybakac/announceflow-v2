from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.tts import TTSJobStatus
from backend.services import tts_service


class _AsyncSessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _build_job(job_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=job_id,
        text_input="Kritik test anons metni",
        language="tr",
        voice_profile="default",
        status=TTSJobStatus.PENDING,
        media_id=None,
        output_path=None,
        processed_at=None,
    )


@pytest.mark.asyncio
async def test_process_tts_job_marks_failed_when_synthesize_raises() -> None:
    job = _build_job(11)
    tts_repo = MagicMock()
    tts_repo.get_by_id = AsyncMock(return_value=job)
    media_repo = MagicMock()
    media_repo.create = AsyncMock()

    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session_factory = MagicMock(return_value=_AsyncSessionContext(session))

    with (
        patch("backend.services.tts_service.TTSJobRepository", return_value=tts_repo),
        patch("backend.services.tts_service.MediaRepository", return_value=media_repo),
        patch(
            "backend.services.tts_service.synthesize",
            new=AsyncMock(side_effect=RuntimeError("synthesize boom")),
        ),
    ):
        await tts_service.process_tts_job(11, session_factory=session_factory)

    assert job.status == TTSJobStatus.FAILED
    assert isinstance(job.processed_at, datetime)
    assert job.processed_at.tzinfo == timezone.utc
    assert session.commit.await_count == 2
    media_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_process_tts_job_marks_failed_when_normalized_artifact_invalid() -> None:
    job = _build_job(21)
    tts_repo = MagicMock()
    tts_repo.get_by_id = AsyncMock(return_value=job)

    media_obj = SimpleNamespace(
        id=88,
        file_hash="",
        file_path="",
        duration=0,
        size_bytes=0,
    )
    media_repo = MagicMock()
    media_repo.create = AsyncMock(return_value=media_obj)

    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session_factory = MagicMock(return_value=_AsyncSessionContext(session))

    with (
        patch("backend.services.tts_service.TTSJobRepository", return_value=tts_repo),
        patch("backend.services.tts_service.MediaRepository", return_value=media_repo),
        patch(
            "backend.services.tts_service.synthesize",
            new=AsyncMock(return_value=Path("/tmp/fake_tts.wav")),
        ),
        patch(
            "backend.services.tts_service.media_service.normalize_audio",
            new=AsyncMock(),
        ) as normalize_audio_mock,
        patch(
            "backend.services.tts_service.asyncio.to_thread",
            new=AsyncMock(return_value=False),
        ),
    ):
        await tts_service.process_tts_job(21, session_factory=session_factory)

    assert job.status == TTSJobStatus.FAILED
    assert job.processed_at is not None
    assert job.media_id is None
    normalize_audio_mock.assert_awaited_once()
    assert session.commit.await_count == 3


@pytest.mark.asyncio
async def test_process_tts_job_uses_fallback_marker_on_unexpected_error() -> None:
    tts_repo = MagicMock()
    tts_repo.get_by_id = AsyncMock(side_effect=RuntimeError("repo failure"))
    media_repo = MagicMock()

    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session_factory = MagicMock(return_value=_AsyncSessionContext(session))

    with (
        patch("backend.services.tts_service.TTSJobRepository", return_value=tts_repo),
        patch("backend.services.tts_service.MediaRepository", return_value=media_repo),
        patch(
            "backend.services.tts_service._mark_job_failed_with_fresh_session",
            new=AsyncMock(),
        ) as mark_failed_mock,
    ):
        await tts_service.process_tts_job(33, session_factory=session_factory)

    session.rollback.assert_awaited_once()
    mark_failed_mock.assert_awaited_once_with(33, session_factory)
