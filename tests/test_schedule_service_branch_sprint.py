from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.media import MediaType, TargetType
from backend.schemas.schedule import ConflictCheckRequest, ScheduleCreate
from backend.services import schedule_service


def _anons_media(name: str = "anons.mp3", duration: int = 30) -> SimpleNamespace:
    return SimpleNamespace(file_name=name, duration=duration, type=MediaType.ANONS)


@pytest.mark.asyncio
async def test_create_schedule_cron_only_skips_conflict_and_commits() -> None:
    db = cast(AsyncSession, MagicMock())
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    media_repo = MagicMock()
    media_repo.get_by_id = AsyncMock(return_value=_anons_media())

    schedule = SimpleNamespace(
        id=501,
        media_id=77,
        target_type=TargetType.ALL,
        target_id=None,
        target_group=None,
        play_at=None,
        cron_expression="*/5 * * * *",
        end_time=None,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    schedule_repo = MagicMock()
    schedule_repo.create = AsyncMock(return_value=schedule)

    data = ScheduleCreate(
        media_id=77,
        target_type=TargetType.ALL,
        cron_expression="*/5 * * * *",
    )

    with (
        patch.object(schedule_service, "MediaRepository", return_value=media_repo),
        patch.object(
            schedule_service,
            "ScheduleRepository",
            return_value=schedule_repo,
        ),
        patch.object(
            schedule_service,
            "_check_and_raise_conflict",
            new=AsyncMock(),
        ) as check_conflict,
    ):
        resp = await schedule_service.create_schedule(db, data)

    assert resp.id == 501
    assert resp.cron_expression == "*/5 * * * *"
    assert resp.play_at is None
    check_conflict.assert_not_awaited()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(schedule)


@pytest.mark.asyncio
async def test_check_and_raise_conflict_returns_http_409_payload() -> None:
    now = datetime.now(timezone.utc)
    conflict_schedule = SimpleNamespace(
        id=42,
        media_id=99,
        target_type=TargetType.BRANCH,
        target_id=7,
        target_group=None,
        play_at=now,
        cron_expression=None,
        end_time=now + timedelta(seconds=15),
        is_active=True,
        created_at=now - timedelta(minutes=1),
    )
    conflict_media = SimpleNamespace(file_name="camp.mp3", duration=15)

    schedule_repo = MagicMock()
    schedule_repo.find_overlapping_one_time = AsyncMock(
        return_value=(conflict_schedule, conflict_media)
    )

    with pytest.raises(HTTPException) as exc:
        await schedule_service._check_and_raise_conflict(
            schedule_repo=schedule_repo,
            media_repo=MagicMock(),
            play_at=now,
            duration=15,
            target_type=TargetType.BRANCH,
            target_id=7,
            target_group=None,
        )

    assert exc.value.status_code == 409
    detail = cast(dict, exc.value.detail)
    assert detail["message"].startswith("Seçtiğiniz zaman diliminde")
    assert detail["conflicting_schedule"]["id"] == 42
    assert detail["conflicting_schedule"]["media_id"] == 99
    assert detail["conflicting_schedule"]["media_file_name"] == "camp.mp3"


@pytest.mark.asyncio
async def test_update_schedule_returns_404_when_schedule_missing() -> None:
    db = cast(AsyncSession, MagicMock())
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    schedule_repo = MagicMock()
    schedule_repo.get_by_id = AsyncMock(return_value=None)

    with patch.object(schedule_service, "ScheduleRepository", return_value=schedule_repo):
        with pytest.raises(HTTPException) as exc:
            await schedule_service.update_schedule(
                db=db,
                schedule_id=404,
                data=schedule_service.ScheduleUpdate(is_active=True),
            )

    assert exc.value.status_code == 404
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_schedule_returns_404_when_schedule_missing() -> None:
    db = cast(AsyncSession, MagicMock())
    db.commit = AsyncMock()

    schedule_repo = MagicMock()
    schedule_repo.get_by_id = AsyncMock(return_value=None)

    with patch.object(schedule_service, "ScheduleRepository", return_value=schedule_repo):
        with pytest.raises(HTTPException) as exc:
            await schedule_service.delete_schedule(db=db, schedule_id=404)

    assert exc.value.status_code == 404
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_conflict_returns_has_conflict_false_when_no_overlap() -> None:
    db = cast(AsyncSession, MagicMock())
    now = datetime.now(timezone.utc)

    media_repo = MagicMock()
    media_repo.get_by_id = AsyncMock(return_value=_anons_media(duration=20))
    schedule_repo = MagicMock()
    schedule_repo.find_overlapping_one_time = AsyncMock(return_value=None)

    data = ConflictCheckRequest(
        media_id=1,
        play_at=now,
        target_type=TargetType.ALL,
    )

    with (
        patch.object(schedule_service, "MediaRepository", return_value=media_repo),
        patch.object(schedule_service, "ScheduleRepository", return_value=schedule_repo),
    ):
        resp = await schedule_service.check_conflict(db=db, data=data)

    assert resp.has_conflict is False
    assert resp.conflicting_schedule is None


@pytest.mark.asyncio
async def test_check_conflict_returns_has_conflict_true_when_overlap_exists() -> None:
    db = cast(AsyncSession, MagicMock())
    now = datetime.now(timezone.utc)

    media_repo = MagicMock()
    media_repo.get_by_id = AsyncMock(return_value=_anons_media(duration=45))
    schedule_repo = MagicMock()
    schedule_repo.find_overlapping_one_time = AsyncMock(
        return_value=(
            SimpleNamespace(
                id=8,
                media_id=3,
                target_type=TargetType.ALL,
                target_id=None,
                target_group=None,
                play_at=now,
                cron_expression=None,
                end_time=now + timedelta(seconds=45),
                is_active=True,
                created_at=now - timedelta(seconds=5),
            ),
            SimpleNamespace(file_name="warn.mp3", duration=45),
        )
    )

    data = ConflictCheckRequest(
        media_id=1,
        play_at=now,
        target_type=TargetType.ALL,
        exclude_schedule_id=55,
    )

    with (
        patch.object(schedule_service, "MediaRepository", return_value=media_repo),
        patch.object(schedule_service, "ScheduleRepository", return_value=schedule_repo),
    ):
        resp = await schedule_service.check_conflict(db=db, data=data)

    assert resp.has_conflict is True
    assert resp.conflicting_schedule is not None
    assert resp.conflicting_schedule.id == 8
    kwargs = schedule_repo.find_overlapping_one_time.await_args.kwargs
    assert kwargs["exclude_id"] == 55
