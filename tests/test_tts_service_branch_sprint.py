from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.tts import TTSJobStatus
from backend.services import tts_service
from backend.services.voice_profile_resolver import VoiceProfileResolutionError


class _AsyncSessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_assert_tts_runtime_supported_raises_on_mismatch() -> None:
    with patch.object(tts_service.sys, "version_info", (3, 10, 12)):
        with pytest.raises(RuntimeError, match="requires Python"):
            tts_service._assert_tts_runtime_supported()


@pytest.mark.asyncio
async def test_get_or_load_model_sync_uses_singleton_cache() -> None:
    sentinel_model = object()
    with (
        patch.object(tts_service, "_tts_model", None),
        patch.object(tts_service, "_load_model", return_value=sentinel_model) as load_mock,
    ):
        first = tts_service._get_or_load_model_sync()
        second = tts_service._get_or_load_model_sync()

    assert first is sentinel_model
    assert second is sentinel_model
    load_mock.assert_called_once()


@pytest.mark.asyncio
async def test_get_model_delegates_to_thread_pool() -> None:
    with patch(
        "backend.services.tts_service.asyncio.to_thread",
        new=AsyncMock(return_value="model-from-thread"),
    ) as to_thread_mock:
        result = await tts_service.get_model()

    assert result == "model-from-thread"
    to_thread_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_synthesize_success_path_returns_wav_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tts_service.settings, "MEDIA_TEMP_PATH", str(tmp_path))
    fake_model = object()

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    with (
        patch("backend.services.tts_service.get_model", new=AsyncMock(return_value=fake_model)),
        patch("backend.services.tts_service.resolve_builtin_speaker", return_value="speaker_1"),
        patch("backend.services.tts_service.uuid.uuid4", return_value="branch-test-id"),
        patch("backend.services.tts_service._synthesize_locked", return_value="ok") as synth_mock,
        patch("backend.services.tts_service.asyncio.to_thread", new=AsyncMock(side_effect=fake_to_thread)),
    ):
        wav_path = await tts_service.synthesize(
            text="Merhaba",
            language="tr",
            voice_profile="default",
            job_id=1,
        )

    assert wav_path == tmp_path / "branch-test-id" / "tts_output.wav"
    synth_mock.assert_called_once()


@pytest.mark.asyncio
async def test_synthesize_raises_when_voice_profile_resolution_fails() -> None:
    err = VoiceProfileResolutionError(
        reason_code="PROFILE_NOT_FOUND",
        detail="missing profile",
        registry_path="/tmp/voice_profiles.json",
    )
    with (
        patch("backend.services.tts_service.get_model", new=AsyncMock(return_value=object())),
        patch("backend.services.tts_service.resolve_builtin_speaker", side_effect=err),
    ):
        with pytest.raises(VoiceProfileResolutionError):
            await tts_service.synthesize(
                text="x",
                language="tr",
                voice_profile="missing",
                job_id=2,
            )


@pytest.mark.asyncio
async def test_mark_job_failed_with_fresh_session_rolls_back_on_commit_error() -> None:
    job = SimpleNamespace(status=TTSJobStatus.PENDING, processed_at=None)
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=job)

    session = AsyncMock()
    session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    session.rollback = AsyncMock()
    session_factory = MagicMock(return_value=_AsyncSessionContext(session))

    with patch("backend.services.tts_service.TTSJobRepository", return_value=repo):
        await tts_service._mark_job_failed_with_fresh_session(55, session_factory)

    assert job.status == TTSJobStatus.FAILED
    assert isinstance(job.processed_at, datetime)
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_tts_job_returns_when_job_not_found() -> None:
    tts_repo = MagicMock()
    tts_repo.get_by_id = AsyncMock(return_value=None)
    media_repo = MagicMock()

    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session_factory = MagicMock(return_value=_AsyncSessionContext(session))

    with (
        patch("backend.services.tts_service.TTSJobRepository", return_value=tts_repo),
        patch("backend.services.tts_service.MediaRepository", return_value=media_repo),
    ):
        await tts_service.process_tts_job(987, session_factory=session_factory)

    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_tts_job_marks_done_on_happy_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tts_service.settings, "MEDIA_STORAGE_PATH", str(tmp_path))

    job = SimpleNamespace(
        id=66,
        text_input="Mutlu yol",
        language="tr",
        voice_profile="default",
        status=TTSJobStatus.PENDING,
        media_id=None,
        output_path=None,
        processed_at=None,
    )
    media = SimpleNamespace(
        id=99,
        file_hash="ready-hash",
        file_path="",
        duration=0,
        size_bytes=0,
    )

    final_output = tmp_path / "99.mp3"
    final_output.write_bytes(b"ok")

    tts_repo = MagicMock()
    tts_repo.get_by_id = AsyncMock(return_value=job)
    media_repo = MagicMock()
    media_repo.create = AsyncMock(return_value=media)

    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session_factory = MagicMock(return_value=_AsyncSessionContext(session))

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    with (
        patch("backend.services.tts_service.TTSJobRepository", return_value=tts_repo),
        patch("backend.services.tts_service.MediaRepository", return_value=media_repo),
        patch(
            "backend.services.tts_service.synthesize",
            new=AsyncMock(return_value=Path("/tmp/fake.wav")),
        ),
        patch(
            "backend.services.tts_service.media_service.normalize_audio",
            new=AsyncMock(),
        ),
        patch(
            "backend.services.tts_service.asyncio.to_thread",
            new=AsyncMock(side_effect=fake_to_thread),
        ),
    ):
        await tts_service.process_tts_job(66, session_factory=session_factory)

    assert job.status == TTSJobStatus.DONE
    assert job.media_id == 99
    assert job.output_path == str(final_output)
    assert job.processed_at is not None
    assert session.commit.await_count == 3
