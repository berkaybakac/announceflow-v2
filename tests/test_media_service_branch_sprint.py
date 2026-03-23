from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile

from backend.core.settings import settings
from backend.services import media_service


class _FakeUploadFile:
    def __init__(self, filename: str, chunks: list[bytes]) -> None:
        self.filename = filename
        self._chunks = list(chunks)

    async def read(self, _size: int) -> bytes:
        if self._chunks:
            return self._chunks.pop(0)
        return b""


class _AsyncSessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_save_upload_to_temp_rejects_path_traversal() -> None:
    upload = _FakeUploadFile("../evil.mp3", [b"payload"])
    with pytest.raises(ValueError, match="Geçersiz dosya adı"):
        await media_service.save_upload_to_temp(cast(UploadFile, upload))


@pytest.mark.asyncio
async def test_save_upload_to_temp_enforces_max_size_and_cleans_temp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 0)
    upload = _FakeUploadFile("oversize.mp3", [b"x"])

    with pytest.raises(ValueError, match="maksimum boyutu aşıyor"):
        await media_service.save_upload_to_temp(cast(UploadFile, upload))

    temp_root = Path(settings.MEDIA_TEMP_PATH)
    assert list(temp_root.iterdir()) == []


@pytest.mark.asyncio
async def test_save_upload_to_temp_writes_chunks_successfully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    upload = _FakeUploadFile(r"folder\safe_song.mp3", [b"abc", b"def"])

    dest = await media_service.save_upload_to_temp(cast(UploadFile, upload))
    assert dest.name == "safe_song.mp3"
    assert dest.read_bytes() == b"abcdef"


@pytest.mark.asyncio
async def test_probe_audio_returns_no_audio_when_ffprobe_missing() -> None:
    with patch(
        "backend.services.media_service.asyncio.create_subprocess_exec",
        new=AsyncMock(side_effect=FileNotFoundError),
    ):
        result = await media_service.probe_audio(Path("/tmp/any.mp3"))

    assert result == {"has_audio": False, "duration_seconds": 0}


@pytest.mark.asyncio
async def test_probe_audio_returns_no_audio_on_invalid_json() -> None:
    proc = SimpleNamespace(
        returncode=0,
        communicate=AsyncMock(return_value=(b"not-json", b"")),
    )
    with patch(
        "backend.services.media_service.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ):
        result = await media_service.probe_audio(Path("/tmp/any.mp3"))

    assert result == {"has_audio": False, "duration_seconds": 0}


@pytest.mark.asyncio
async def test_probe_audio_handles_bad_duration_but_keeps_stream_detection() -> None:
    proc = SimpleNamespace(
        returncode=0,
        communicate=AsyncMock(
            return_value=(
                b'{"streams":[{"codec_name":"mp3"}],"format":{"duration":"nan"}}',
                b"",
            )
        ),
    )
    with patch(
        "backend.services.media_service.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ):
        result = await media_service.probe_audio(Path("/tmp/any.mp3"))

    assert result == {"has_audio": True, "duration_seconds": 0}


@pytest.mark.asyncio
async def test_normalize_audio_success_when_media_record_missing_still_commits(
    tmp_path: Path,
) -> None:
    temp_dir = tmp_path / "incoming"
    temp_dir.mkdir()
    temp_path = temp_dir / "upload.wav"
    temp_path.write_bytes(b"fake-wav")

    output_path = tmp_path / "media" / "404.mp3"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake-mp3")

    proc = SimpleNamespace(
        returncode=0,
        communicate=AsyncMock(return_value=(b"", b"")),
    )

    media_repo = MagicMock()
    media_repo.get_by_id = AsyncMock(return_value=None)
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session_factory = MagicMock(return_value=_AsyncSessionContext(session))

    with (
        patch(
            "backend.services.media_service.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ),
        patch(
            "backend.services.media_service.compute_sha256",
            return_value="b" * 64,
        ),
        patch(
            "backend.services.media_service.probe_audio",
            new=AsyncMock(return_value={"has_audio": True, "duration_seconds": 7}),
        ),
        patch("backend.services.media_service.MediaRepository", return_value=media_repo),
    ):
        await media_service.normalize_audio(
            temp_path,
            output_path,
            media_id=404,
            session_factory=session_factory,
        )

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
