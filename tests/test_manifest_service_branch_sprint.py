from datetime import time
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.branch import Branch
from backend.schemas.manifest import SyncConfirmRequest
from backend.services import manifest_service


async def test_build_manifest_truncates_and_builds_settings_payload(
    monkeypatch,
) -> None:
    branch = SimpleNamespace(id=7, group_tag="g1")
    music_rows = [
        SimpleNamespace(
            id=11,
            file_name="m1.mp3",
            file_hash="h1",
            type=SimpleNamespace(value="MUSIC"),
            size_bytes=100,
        ),
        SimpleNamespace(
            id=12,
            file_name="m2.mp3",
            file_hash="h2",
            type=SimpleNamespace(value="MUSIC"),
            size_bytes=200,
        ),
    ]
    sched_rows = [
        (
            SimpleNamespace(id=21, play_at=None, cron_expression="0 9 * * *", end_time=None),
            SimpleNamespace(id=31, file_name="a1.mp3", file_hash="ha1", size_bytes=50),
        ),
        (
            SimpleNamespace(id=22, play_at=None, cron_expression="0 10 * * *", end_time=None),
            SimpleNamespace(id=32, file_name="a2.mp3", file_hash="ha2", size_bytes=55),
        ),
    ]
    branch_with_settings = SimpleNamespace(
        settings=SimpleNamespace(
            work_start=time(9, 0),
            work_end=time(22, 0),
            loop_mode="shuffle_loop",
        ),
        volume_music=65,
        volume_announce=80,
    )

    media_repo = MagicMock()
    media_repo.get_music_for_branch = AsyncMock(return_value=music_rows)
    schedule_repo = MagicMock()
    schedule_repo.get_schedules_for_branch_with_media = AsyncMock(return_value=sched_rows)
    branch_repo = MagicMock()
    branch_repo.get_with_settings = AsyncMock(return_value=branch_with_settings)
    db = cast(AsyncSession, MagicMock())

    monkeypatch.setattr("backend.core.settings.settings.MANIFEST_MAX_FILES", 1)

    with (
        patch.object(manifest_service, "MediaRepository", return_value=media_repo),
        patch.object(manifest_service, "ScheduleRepository", return_value=schedule_repo),
        patch.object(manifest_service, "BranchRepository", return_value=branch_repo),
        patch.object(manifest_service.logger, "warning") as warning_mock,
    ):
        resp = await manifest_service.build_manifest(
            branch=cast(Branch, branch),
            db=db,
        )

    assert resp.branch_id == 7
    assert len(resp.music) == 1
    assert resp.music[0].id == 11
    assert len(resp.announcements) == 1
    assert resp.announcements[0].id == 21
    assert resp.settings is not None
    assert resp.settings.work_start == "09:00"
    assert resp.settings.work_end == "22:00"
    assert resp.settings.volume_music == 65
    assert warning_mock.call_count == 2


async def test_build_manifest_returns_settings_none_when_branch_settings_missing() -> None:
    branch = SimpleNamespace(id=3, group_tag=None)
    media_repo = MagicMock()
    media_repo.get_music_for_branch = AsyncMock(return_value=[])
    schedule_repo = MagicMock()
    schedule_repo.get_schedules_for_branch_with_media = AsyncMock(return_value=[])
    branch_repo = MagicMock()
    branch_repo.get_with_settings = AsyncMock(return_value=None)
    db = cast(AsyncSession, MagicMock())

    with (
        patch.object(manifest_service, "MediaRepository", return_value=media_repo),
        patch.object(manifest_service, "ScheduleRepository", return_value=schedule_repo),
        patch.object(manifest_service, "BranchRepository", return_value=branch_repo),
    ):
        resp = await manifest_service.build_manifest(
            branch=cast(Branch, branch),
            db=db,
        )

    assert resp.branch_id == 3
    assert resp.music == []
    assert resp.announcements == []
    assert resp.settings is None


async def test_confirm_sync_returns_not_found_payload_when_branch_missing() -> None:
    repo = MagicMock()
    repo.update_last_sync = AsyncMock(return_value=False)
    db = cast(AsyncSession, MagicMock())

    with patch.object(manifest_service, "BranchRepository", return_value=repo):
        resp = await manifest_service.confirm_sync(
            branch_id=404,
            body=SyncConfirmRequest(synced_files_count=1, status="ok"),
            db=db,
        )

    assert resp.ok is False
    assert resp.message == "Branch bulunamadı"


async def test_confirm_sync_returns_ok_payload_on_success() -> None:
    repo = MagicMock()
    repo.update_last_sync = AsyncMock(return_value=True)
    db = cast(AsyncSession, MagicMock())

    with patch.object(manifest_service, "BranchRepository", return_value=repo):
        resp = await manifest_service.confirm_sync(
            branch_id=9,
            body=SyncConfirmRequest(synced_files_count=5, status="partial"),
            db=db,
        )

    assert resp.ok is True
    assert "5 dosya" in resp.message
    assert "partial" in resp.message
