from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services import media_service


class _AsyncSessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_normalize_audio_ffmpeg_failure_returns_without_db_session(
    tmp_path: Path,
) -> None:
    temp_dir = tmp_path / "incoming"
    temp_dir.mkdir()
    temp_path = temp_dir / "upload.wav"
    temp_path.write_bytes(b"fake-wav")
    output_path = tmp_path / "media" / "1.mp3"

    proc = SimpleNamespace(
        returncode=1,
        communicate=AsyncMock(return_value=(b"", b"ffmpeg failed")),
    )
    session_factory = MagicMock()

    with patch(
        "backend.services.media_service.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ):
        await media_service.normalize_audio(
            temp_path,
            output_path,
            media_id=12,
            session_factory=session_factory,
        )

    assert temp_dir.exists() is False
    session_factory.assert_not_called()


@pytest.mark.asyncio
async def test_normalize_audio_db_commit_error_rolls_back_and_swallows_exception(
    tmp_path: Path,
) -> None:
    temp_dir = tmp_path / "incoming"
    temp_dir.mkdir()
    temp_path = temp_dir / "upload.wav"
    temp_path.write_bytes(b"fake-wav")

    output_path = tmp_path / "media" / "77.mp3"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake-mp3")

    proc = SimpleNamespace(
        returncode=0,
        communicate=AsyncMock(return_value=(b"", b"")),
    )
    media_obj = SimpleNamespace(file_hash="", file_path="", duration=0, size_bytes=0)
    media_repo = MagicMock()
    media_repo.get_by_id = AsyncMock(return_value=media_obj)

    session = AsyncMock()
    session.commit = AsyncMock(side_effect=RuntimeError("db write failed"))
    session.rollback = AsyncMock()
    session_factory = MagicMock(return_value=_AsyncSessionContext(session))

    with (
        patch(
            "backend.services.media_service.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ),
        patch(
            "backend.services.media_service.compute_sha256",
            return_value="a" * 64,
        ),
        patch(
            "backend.services.media_service.probe_audio",
            new=AsyncMock(return_value={"has_audio": True, "duration_seconds": 13}),
        ),
        patch(
            "backend.services.media_service.MediaRepository",
            return_value=media_repo,
        ),
    ):
        await media_service.normalize_audio(
            temp_path,
            output_path,
            media_id=77,
            session_factory=session_factory,
        )

    session.commit.assert_awaited_once()
    session.rollback.assert_awaited_once()
    assert media_obj.file_hash == "a" * 64
    assert media_obj.file_path == str(output_path)
    assert media_obj.duration == 13
    assert media_obj.size_bytes == len(b"fake-mp3")
