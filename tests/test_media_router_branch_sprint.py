from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.branch import Branch
from backend.models.user import User
from backend.routers import media as media_router
from backend.schemas.tts import TTSRequest


async def test_upload_media_returns_413_when_temp_save_raises_value_error() -> None:
    upload = UploadFile(filename="too_big.mp3", file=BytesIO(b"data"))
    db = cast(AsyncSession, MagicMock())

    with patch.object(
        media_router.media_service,
        "save_upload_to_temp",
        new=AsyncMock(side_effect=ValueError("File too large")),
    ):
        with pytest.raises(HTTPException) as exc:
            await media_router.upload_media(
                background_tasks=BackgroundTasks(),
                file=upload,
                media_type="MUSIC",
                db=db,
                current_user=cast(User, SimpleNamespace(id=1)),
            )

    assert exc.value.status_code == 413
    assert "File too large" in str(exc.value.detail)


async def test_upload_media_success_creates_record_and_schedules_normalization() -> None:
    upload = UploadFile(filename="song.mp3", file=BytesIO(b"audio"))
    temp_path = Path("/tmp/fake-upload/song.mp3")
    db = cast(AsyncSession, MagicMock())
    repo = MagicMock()

    async def _create(media):
        media.id = 321
        return media

    repo.get_by_hash = AsyncMock(return_value=None)
    repo.create = AsyncMock(side_effect=_create)
    background_tasks = BackgroundTasks()

    with (
        patch.object(
            media_router.media_service,
            "save_upload_to_temp",
            new=AsyncMock(return_value=temp_path),
        ),
        patch.object(
            media_router.media_service,
            "probe_audio",
            new=AsyncMock(return_value={"has_audio": True, "duration_seconds": 120}),
        ),
        patch.object(
            media_router.media_service,
            "compute_sha256",
            return_value="a" * 64,
        ),
        patch.object(media_router, "MediaRepository", return_value=repo),
    ):
        resp = await media_router.upload_media(
            background_tasks=background_tasks,
            file=upload,
            media_type="MUSIC",
            db=db,
            current_user=cast(User, SimpleNamespace(id=1)),
        )

    assert resp.media_id == 321
    assert resp.file_name == "song.mp3"
    assert resp.status == "processing"
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func == media_router.media_service.normalize_audio


async def test_upload_media_duplicate_hash_returns_409_and_cleans_temp_dir(
    tmp_path: Path,
) -> None:
    upload_dir = tmp_path / "upload-tmp"
    upload_dir.mkdir(parents=True, exist_ok=True)
    temp_path = upload_dir / "dup.mp3"
    temp_path.write_bytes(b"fake-audio")

    upload = UploadFile(filename="dup.mp3", file=BytesIO(b"audio"))
    db = cast(AsyncSession, MagicMock())
    repo = MagicMock()
    repo.get_by_hash = AsyncMock(return_value=SimpleNamespace(id=44))
    repo.create = AsyncMock()

    with (
        patch.object(
            media_router.media_service,
            "save_upload_to_temp",
            new=AsyncMock(return_value=temp_path),
        ),
        patch.object(
            media_router.media_service,
            "probe_audio",
            new=AsyncMock(return_value={"has_audio": True, "duration_seconds": 120}),
        ),
        patch.object(
            media_router.media_service,
            "compute_sha256",
            return_value="dup-hash",
        ),
        patch.object(media_router, "MediaRepository", return_value=repo),
    ):
        with pytest.raises(HTTPException) as exc:
            await media_router.upload_media(
                background_tasks=BackgroundTasks(),
                file=upload,
                media_type="MUSIC",
                db=db,
                current_user=cast(User, SimpleNamespace(id=1)),
            )

    assert exc.value.status_code == 409
    assert "media_id=44" in str(exc.value.detail)
    assert not upload_dir.exists()
    repo.create.assert_not_awaited()


async def test_download_media_raises_404_when_media_missing() -> None:
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    db = cast(AsyncSession, MagicMock())

    with patch.object(media_router, "MediaRepository", return_value=repo):
        with pytest.raises(HTTPException) as exc:
            await media_router.download_media(
                media_id=999,
                db=db,
                current_device=cast(Branch, SimpleNamespace(id=10, group_tag=None)),
            )

    assert exc.value.status_code == 404
    assert "Medya bulunamadı" in str(exc.value.detail)


async def test_download_media_raises_403_when_branch_has_no_access(tmp_path: Path) -> None:
    media = SimpleNamespace(file_path=str(tmp_path / "ok.mp3"), file_name="ok.mp3")
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=media)
    repo.is_accessible_for_branch = AsyncMock(return_value=False)
    db = cast(AsyncSession, MagicMock())

    with patch.object(media_router, "MediaRepository", return_value=repo):
        with pytest.raises(HTTPException) as exc:
            await media_router.download_media(
                media_id=5,
                db=db,
                current_device=cast(Branch, SimpleNamespace(id=10, group_tag="g1")),
            )

    assert exc.value.status_code == 403
    assert "erişim yetkiniz yok" in str(exc.value.detail)


async def test_download_media_raises_404_when_file_is_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.mp3"
    media = SimpleNamespace(file_path=str(missing_path), file_name="missing.mp3")
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=media)
    repo.is_accessible_for_branch = AsyncMock(return_value=True)
    db = cast(AsyncSession, MagicMock())

    with patch.object(media_router, "MediaRepository", return_value=repo):
        with pytest.raises(HTTPException) as exc:
            await media_router.download_media(
                media_id=6,
                db=db,
                current_device=cast(Branch, SimpleNamespace(id=10, group_tag="g1")),
            )

    assert exc.value.status_code == 404
    assert "Medya dosyası bulunamadı" in str(exc.value.detail)


async def test_download_media_returns_file_response_when_access_granted(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "ok.mp3"
    file_path.write_bytes(b"ID3-data")
    media = SimpleNamespace(file_path=str(file_path), file_name="ok.mp3")
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=media)
    repo.is_accessible_for_branch = AsyncMock(return_value=True)
    db = cast(AsyncSession, MagicMock())

    with patch.object(media_router, "MediaRepository", return_value=repo):
        resp = await media_router.download_media(
            media_id=7,
            db=db,
            current_device=cast(Branch, SimpleNamespace(id=10, group_tag="g1")),
        )

    assert resp.path == file_path
    assert resp.filename == "ok.mp3"


async def test_create_tts_job_commits_and_schedules_background_task() -> None:
    now = datetime.now(timezone.utc)
    job = SimpleNamespace(
        id=55,
        text_input="Merhaba",
        voice_profile="default",
        status="PENDING",
        media_id=None,
        created_at=now,
        processed_at=None,
    )
    repo = MagicMock()
    repo.create = AsyncMock(return_value=job)
    db = cast(AsyncSession, MagicMock())
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    background_tasks = BackgroundTasks()

    with patch.object(media_router, "TTSJobRepository", return_value=repo):
        resp = await media_router.create_tts_job(
            background_tasks=background_tasks,
            body=TTSRequest(text="Merhaba"),
            db=db,
            current_user=cast(User, SimpleNamespace(id=1)),
        )

    assert resp.id == 55
    assert resp.status == "PENDING"
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(job)
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func == media_router.tts_service.process_tts_job


async def test_get_tts_job_not_found_returns_404() -> None:
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    db = cast(AsyncSession, MagicMock())

    with patch.object(media_router, "TTSJobRepository", return_value=repo):
        with pytest.raises(HTTPException) as exc:
            await media_router.get_tts_job(
                job_id=404,
                db=db,
                current_user=cast(User, SimpleNamespace(id=1)),
            )

    assert exc.value.status_code == 404
    assert "TTS job bulunamadı" in str(exc.value.detail)


async def test_get_tts_job_success_returns_model() -> None:
    now = datetime.now(timezone.utc)
    job = SimpleNamespace(
        id=99,
        text_input="Deneme",
        voice_profile="default",
        status="DONE",
        media_id=7,
        created_at=now,
        processed_at=now,
    )
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=job)
    db = cast(AsyncSession, MagicMock())

    with patch.object(media_router, "TTSJobRepository", return_value=repo):
        resp = await media_router.get_tts_job(
            job_id=99,
            db=db,
            current_user=cast(User, SimpleNamespace(id=1)),
        )

    assert resp.id == 99
    assert resp.media_id == 7
    assert resp.status == "DONE"
