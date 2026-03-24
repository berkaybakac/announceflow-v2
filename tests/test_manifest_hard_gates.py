from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import create_access_token
from backend.models.branch import Branch
from backend.models.media import MediaFile, MediaTarget, MediaType, TargetType
from backend.models.schedule import Schedule
from backend.repositories.media_repository import MediaRepository
from backend.repositories.schedule_repository import ScheduleRepository


def _device_token(branch: Branch) -> str:
    return create_access_token({"sub": str(branch.id), "type": "device"})


async def _create_media(
    db: AsyncSession,
    file_name: str,
    file_hash: str,
    media_type: MediaType,
) -> MediaFile:
    media = MediaFile(
        file_name=file_name,
        file_path=f"/data/media/{file_name}",
        file_hash=file_hash,
        type=media_type,
        duration=60,
        size_bytes=1024,
    )
    db.add(media)
    await db.flush()
    await db.refresh(media)
    return media


async def _assign_branch_target(
    db: AsyncSession,
    media: MediaFile,
    branch_id: int,
) -> MediaTarget:
    target = MediaTarget(
        media_id=media.id,
        target_type=TargetType.BRANCH,
        target_id=branch_id,
    )
    db.add(target)
    await db.flush()
    return target


async def _create_schedule(
    db: AsyncSession,
    media: MediaFile,
    branch_id: int,
) -> Schedule:
    schedule = Schedule(
        media_id=media.id,
        target_type=TargetType.BRANCH,
        target_id=branch_id,
        is_active=True,
        cron_expression="0 14 * * *",
    )
    db.add(schedule)
    await db.flush()
    await db.refresh(schedule)
    return schedule


@pytest.mark.asyncio
async def test_media_acl_query_uses_single_execute_call(
    db_session: AsyncSession,
    test_branch: Branch,
):
    media_a = await _create_media(
        db_session,
        "music_a.mp3",
        "ha",
        MediaType.MUSIC,
    )
    media_b = await _create_media(
        db_session,
        "music_b.mp3",
        "hb",
        MediaType.MUSIC,
    )
    await _assign_branch_target(db_session, media_a, test_branch.id)
    await _assign_branch_target(db_session, media_b, test_branch.id)
    await db_session.commit()

    repo = MediaRepository(db_session)
    original_execute = db_session.execute
    execute_count = 0

    async def counted_execute(*args, **kwargs):
        nonlocal execute_count
        execute_count += 1
        return await original_execute(*args, **kwargs)

    with patch.object(db_session, "execute", new=counted_execute):
        rows = await repo.get_music_for_branch(
            test_branch.id,
            test_branch.group_tag,
            limit=201,
        )

    assert len(rows) == 2
    assert execute_count == 1


@pytest.mark.asyncio
async def test_schedule_acl_query_single_execute_and_anons_only(
    db_session: AsyncSession,
    test_branch: Branch,
):
    anons = await _create_media(
        db_session,
        "anons_ok.mp3",
        "anons_hash",
        MediaType.ANONS,
    )
    music = await _create_media(
        db_session,
        "music_should_not_pass.mp3",
        "music_hash",
        MediaType.MUSIC,
    )
    await _create_schedule(db_session, anons, test_branch.id)
    await _create_schedule(db_session, music, test_branch.id)
    await db_session.commit()

    repo = ScheduleRepository(db_session)
    original_execute = db_session.execute
    execute_count = 0

    async def counted_execute(*args, **kwargs):
        nonlocal execute_count
        execute_count += 1
        return await original_execute(*args, **kwargs)

    with patch.object(db_session, "execute", new=counted_execute):
        rows = await repo.get_schedules_for_branch_with_media(
            test_branch.id,
            test_branch.group_tag,
            limit=201,
        )

    assert execute_count == 1
    assert len(rows) == 1
    _, media = rows[0]
    assert media.type == MediaType.ANONS
    assert media.file_name == "anons_ok.mp3"


@pytest.mark.asyncio
async def test_manifest_graceful_truncates_music_and_logs_warning(
    client: AsyncClient,
    db_session: AsyncSession,
    test_branch: Branch,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "backend.core.settings.settings.MANIFEST_MAX_FILES",
        2,
    )

    for idx in range(3):
        media = await _create_media(
            db_session,
            f"music_{idx}.mp3",
            f"hash_{idx}",
            MediaType.MUSIC,
        )
        await _assign_branch_target(db_session, media, test_branch.id)

    await db_session.commit()
    token = _device_token(test_branch)

    with patch("backend.services.manifest_service.logger.warning") as warning_mock:
        resp = await client.get(
            f"/api/v1/manifest/{test_branch.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["music"]) == 2

    warning_mock.assert_called_once()
    assert warning_mock.call_args.kwargs["extra"]["item_type"] == "music"
