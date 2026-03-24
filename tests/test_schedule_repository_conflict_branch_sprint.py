from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.media import MediaFile, MediaType, TargetType
from backend.models.schedule import Schedule
from backend.repositories.schedule_repository import ScheduleRepository


async def _create_anons_media(
    db: AsyncSession,
    file_name: str,
    file_hash: str,
) -> MediaFile:
    media = MediaFile(
        file_name=file_name,
        file_path=f"/data/media/{file_name}",
        file_hash=file_hash,
        type=MediaType.ANONS,
        duration=60,
        size_bytes=1024,
    )
    db.add(media)
    await db.flush()
    await db.refresh(media)
    return media


async def _create_one_time_schedule(
    db: AsyncSession,
    media_id: int,
    target_type: TargetType,
    *,
    play_at: datetime | None,
    end_time: datetime | None,
    target_id: int | None = None,
    target_group: str | None = None,
    is_active: bool = True,
) -> Schedule:
    schedule = Schedule(
        media_id=media_id,
        target_type=target_type,
        target_id=target_id,
        target_group=target_group,
        play_at=play_at,
        cron_expression=None,
        end_time=end_time,
        is_active=is_active,
    )
    db.add(schedule)
    await db.flush()
    await db.refresh(schedule)
    return schedule


@pytest.mark.asyncio
async def test_find_overlap_candidate_all_conflicts_with_branch_target(
    db_session: AsyncSession,
) -> None:
    media = await _create_anons_media(db_session, "all_vs_branch.mp3", "h-all-branch")
    start = datetime.now(timezone.utc) + timedelta(hours=2)
    end = start + timedelta(seconds=60)
    existing = await _create_one_time_schedule(
        db_session,
        media.id,
        TargetType.BRANCH,
        target_id=10,
        play_at=start,
        end_time=end,
    )
    await db_session.commit()

    repo = ScheduleRepository(db_session)
    row = await repo.find_overlapping_one_time(
        play_at=start + timedelta(seconds=10),
        end_time=end + timedelta(seconds=10),
        target_type=TargetType.ALL,
        target_id=None,
        target_group=None,
    )

    assert row is not None
    schedule, _ = row
    assert schedule.id == existing.id


@pytest.mark.asyncio
async def test_find_overlap_branch_candidate_matches_only_same_branch(
    db_session: AsyncSession,
) -> None:
    media = await _create_anons_media(db_session, "branch_match.mp3", "h-branch-match")
    start = datetime.now(timezone.utc) + timedelta(hours=3)
    end = start + timedelta(seconds=90)
    await _create_one_time_schedule(
        db_session,
        media.id,
        TargetType.BRANCH,
        target_id=33,
        play_at=start,
        end_time=end,
    )
    await db_session.commit()

    repo = ScheduleRepository(db_session)
    same_branch = await repo.find_overlapping_one_time(
        play_at=start + timedelta(seconds=5),
        end_time=end + timedelta(seconds=5),
        target_type=TargetType.BRANCH,
        target_id=33,
        target_group=None,
    )
    other_branch = await repo.find_overlapping_one_time(
        play_at=start + timedelta(seconds=5),
        end_time=end + timedelta(seconds=5),
        target_type=TargetType.BRANCH,
        target_id=34,
        target_group=None,
    )

    assert same_branch is not None
    assert other_branch is None


@pytest.mark.asyncio
async def test_find_overlap_group_candidate_matches_only_same_group(
    db_session: AsyncSession,
) -> None:
    media = await _create_anons_media(db_session, "group_match.mp3", "h-group-match")
    start = datetime.now(timezone.utc) + timedelta(hours=4)
    end = start + timedelta(seconds=75)
    await _create_one_time_schedule(
        db_session,
        media.id,
        TargetType.GROUP,
        target_group="izmir",
        play_at=start,
        end_time=end,
    )
    await db_session.commit()

    repo = ScheduleRepository(db_session)
    same_group = await repo.find_overlapping_one_time(
        play_at=start + timedelta(seconds=1),
        end_time=end + timedelta(seconds=1),
        target_type=TargetType.GROUP,
        target_id=None,
        target_group="izmir",
    )
    other_group = await repo.find_overlapping_one_time(
        play_at=start + timedelta(seconds=1),
        end_time=end + timedelta(seconds=1),
        target_type=TargetType.GROUP,
        target_id=None,
        target_group="ankara",
    )

    assert same_group is not None
    assert other_group is None


@pytest.mark.asyncio
async def test_find_overlap_respects_exclude_id(
    db_session: AsyncSession,
) -> None:
    media = await _create_anons_media(db_session, "exclude.mp3", "h-exclude")
    start = datetime.now(timezone.utc) + timedelta(hours=5)
    end = start + timedelta(seconds=30)
    existing = await _create_one_time_schedule(
        db_session,
        media.id,
        TargetType.ALL,
        play_at=start,
        end_time=end,
    )
    await db_session.commit()

    repo = ScheduleRepository(db_session)
    row = await repo.find_overlapping_one_time(
        play_at=start,
        end_time=end,
        target_type=TargetType.ALL,
        target_id=None,
        target_group=None,
        exclude_id=existing.id,
    )

    assert row is None


@pytest.mark.asyncio
async def test_find_overlap_ignores_inactive_schedules(
    db_session: AsyncSession,
) -> None:
    media = await _create_anons_media(db_session, "inactive.mp3", "h-inactive")
    start = datetime.now(timezone.utc) + timedelta(hours=6)
    end = start + timedelta(seconds=120)
    await _create_one_time_schedule(
        db_session,
        media.id,
        TargetType.ALL,
        play_at=start,
        end_time=end,
        is_active=False,
    )
    await db_session.commit()

    repo = ScheduleRepository(db_session)
    row = await repo.find_overlapping_one_time(
        play_at=start + timedelta(seconds=10),
        end_time=end + timedelta(seconds=10),
        target_type=TargetType.ALL,
        target_id=None,
        target_group=None,
    )

    assert row is None


@pytest.mark.asyncio
async def test_find_overlap_ignores_rows_with_null_play_at(
    db_session: AsyncSession,
) -> None:
    media = await _create_anons_media(db_session, "null_play_at.mp3", "h-null-play")
    await _create_one_time_schedule(
        db_session,
        media.id,
        TargetType.ALL,
        play_at=None,
        end_time=None,
        is_active=True,
    )
    await db_session.commit()

    repo = ScheduleRepository(db_session)
    probe_start = datetime.now(timezone.utc) + timedelta(hours=7)
    probe_end = probe_start + timedelta(seconds=10)
    row = await repo.find_overlapping_one_time(
        play_at=probe_start,
        end_time=probe_end,
        target_type=TargetType.ALL,
        target_id=None,
        target_group=None,
    )

    assert row is None
