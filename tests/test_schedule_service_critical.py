from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.models.media import MediaType, TargetType
from backend.schemas.schedule import ConflictCheckRequest, ScheduleCreate, ScheduleUpdate
from backend.services import schedule_service


@pytest.mark.asyncio
async def test_create_schedule_missing_media_returns_422_and_fails_fast() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    media_repo = MagicMock()
    media_repo.get_by_id = AsyncMock(return_value=None)
    schedule_repo = MagicMock()
    schedule_repo.create = AsyncMock()

    data = ScheduleCreate(
        media_id=999,
        target_type=TargetType.ALL,
        play_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    with (
        patch.object(schedule_service, "MediaRepository", return_value=media_repo),
        patch.object(
            schedule_service, "ScheduleRepository", return_value=schedule_repo
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await schedule_service.create_schedule(db, data)

    assert exc.value.status_code == 422
    assert "media_id=999" in str(exc.value.detail)
    schedule_repo.create.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_schedule_xor_violation_returns_422_without_commit() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    existing = SimpleNamespace(
        id=10,
        media_id=1,
        target_type=TargetType.ALL,
        target_id=None,
        target_group=None,
        play_at=datetime.now(timezone.utc) + timedelta(hours=2),
        cron_expression=None,
        end_time=None,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    valid_anons_media = SimpleNamespace(
        file_name="anons.mp3",
        duration=30,
        type=MediaType.ANONS,
    )

    schedule_repo = MagicMock()
    schedule_repo.get_by_id = AsyncMock(return_value=existing)
    media_repo = MagicMock()
    media_repo.get_by_id = AsyncMock(return_value=valid_anons_media)

    data = ScheduleUpdate(play_at=None)

    with (
        patch.object(
            schedule_service, "ScheduleRepository", return_value=schedule_repo
        ),
        patch.object(schedule_service, "MediaRepository", return_value=media_repo),
    ):
        with pytest.raises(HTTPException) as exc:
            await schedule_service.update_schedule(db, 10, data)

    assert exc.value.status_code == 422
    assert "XOR ihlali" in str(exc.value.detail)
    schedule_repo.get_by_id.assert_awaited_once_with(10)
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_conflict_returns_conflicting_schedule_payload() -> None:
    db = AsyncMock()
    now = datetime.now(timezone.utc)

    media_for_duration = SimpleNamespace(
        file_name="input.mp3",
        duration=45,
        type=MediaType.ANONS,
    )
    conflicting_schedule = SimpleNamespace(
        id=42,
        media_id=7,
        target_type=TargetType.BRANCH,
        target_id=3,
        target_group=None,
        play_at=now,
        cron_expression=None,
        end_time=now + timedelta(seconds=45),
        is_active=True,
        created_at=now - timedelta(minutes=5),
    )
    conflicting_media = SimpleNamespace(file_name="kampanya.mp3", duration=45)

    media_repo = MagicMock()
    media_repo.get_by_id = AsyncMock(return_value=media_for_duration)
    schedule_repo = MagicMock()
    schedule_repo.find_overlapping_one_time = AsyncMock(
        return_value=(conflicting_schedule, conflicting_media)
    )

    data = ConflictCheckRequest(
        media_id=1,
        play_at=now,
        target_type=TargetType.BRANCH,
        target_id=3,
    )

    with (
        patch.object(schedule_service, "MediaRepository", return_value=media_repo),
        patch.object(
            schedule_service, "ScheduleRepository", return_value=schedule_repo
        ),
    ):
        response = await schedule_service.check_conflict(db, data)

    assert response.has_conflict is True
    assert response.conflicting_schedule is not None
    assert response.conflicting_schedule.id == 42
    assert response.conflicting_schedule.media_id == 7
    assert response.conflicting_schedule.media_file_name == "kampanya.mp3"
    assert response.conflicting_schedule.media_duration == 45

    kwargs = schedule_repo.find_overlapping_one_time.await_args.kwargs
    assert kwargs["end_time"] == now + timedelta(seconds=45)
    assert kwargs["exclude_id"] is None
