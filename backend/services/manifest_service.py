"""
Manifest Service — Sync Engine (Backend).

Branch'e ait müzik, anons ve ayar bilgilerini tek manifest JSON olarak derler.
Agent'ın sync onayını kaydeder.
"""

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.settings import settings
from backend.models.branch import Branch
from backend.repositories.branch_repository import BranchRepository
from backend.repositories.media_repository import MediaRepository
from backend.repositories.schedule_repository import ScheduleRepository
from backend.schemas.manifest import (
    ManifestMediaItem,
    ManifestResponse,
    ManifestScheduleItem,
    ManifestSettingsItem,
    SyncConfirmRequest,
    SyncConfirmResponse,
)
from shared.logger import get_logger

logger = get_logger(__name__)


def _truncate_for_ram_safety(
    branch_id: int,
    items: Sequence[Any],
    max_files: int,
    item_type: str,
) -> list[Any]:
    if len(items) <= max_files:
        return list(items)

    logger.warning(
        "Branch %s manifest exceeded max files (%s/%s). Truncating to protect RAM.",
        branch_id,
        len(items),
        max_files,
        extra={
            "branch_id": branch_id,
            "count": len(items),
            "max": max_files,
            "item_type": item_type,
        },
    )
    return list(items[:max_files])


async def _fetch_music_files(
    branch: Branch,
    media_repo: MediaRepository,
    fetch_limit: int,
    max_files: int,
) -> list[Any]:
    files = await media_repo.get_music_for_branch(
        branch.id,
        branch.group_tag,
        limit=fetch_limit,
    )
    return _truncate_for_ram_safety(branch.id, files, max_files, "music")


async def _fetch_announcement_rows(
    branch: Branch,
    schedule_repo: ScheduleRepository,
    fetch_limit: int,
    max_files: int,
) -> list[Any]:
    rows = await schedule_repo.get_schedules_for_branch_with_media(
        branch.id,
        branch.group_tag,
        limit=fetch_limit,
    )
    return _truncate_for_ram_safety(branch.id, rows, max_files, "announcements")


def _build_music_items(music_files: Sequence[Any]) -> list[ManifestMediaItem]:
    return [
        ManifestMediaItem(
            id=mf.id,
            file_name=mf.file_name,
            file_hash=mf.file_hash,
            type=mf.type.value,
            size_bytes=mf.size_bytes,
            download_url=f"/api/v1/media/{mf.id}/download",
        )
        for mf in music_files
    ]


def _build_announcement_items(schedule_rows: Sequence[Any]) -> list[ManifestScheduleItem]:
    return [
        ManifestScheduleItem(
            id=sched.id,
            media_id=media.id,
            media_file_name=media.file_name,
            media_file_hash=media.file_hash,
            media_size_bytes=media.size_bytes,
            media_download_url=f"/api/v1/media/{media.id}/download",
            play_at=sched.play_at,
            cron_expression=sched.cron_expression,
            end_time=sched.end_time,
        )
        for sched, media in schedule_rows
    ]


def _build_settings_item(branch_with_settings: Branch | None) -> ManifestSettingsItem | None:
    if branch_with_settings is None or branch_with_settings.settings is None:
        return None
    branch_settings = branch_with_settings.settings
    return ManifestSettingsItem(
        work_start=branch_settings.work_start.strftime("%H:%M"),
        work_end=branch_settings.work_end.strftime("%H:%M"),
        volume_music=branch_with_settings.volume_music,
        volume_announce=branch_with_settings.volume_announce,
        loop_mode=branch_settings.loop_mode,
    )


async def _load_manifest_sources(
    branch: Branch,
    db: AsyncSession,
) -> tuple[list[Any], list[Any], Branch | None]:
    max_files = settings.MANIFEST_MAX_FILES
    fetch_limit = max_files + 1
    media_repo = MediaRepository(db)
    schedule_repo = ScheduleRepository(db)
    branch_repo = BranchRepository(db)
    music_files = await _fetch_music_files(branch, media_repo, fetch_limit, max_files)
    schedule_rows = await _fetch_announcement_rows(
        branch,
        schedule_repo,
        fetch_limit,
        max_files,
    )
    branch_with_settings = await branch_repo.get_with_settings(branch.id)
    return music_files, schedule_rows, branch_with_settings


async def build_manifest(branch: Branch, db: AsyncSession) -> ManifestResponse:
    """Branch için ACL-aware manifest üretir."""
    music_files, schedule_rows, branch_with_settings = await _load_manifest_sources(
        branch,
        db,
    )
    return ManifestResponse(
        branch_id=branch.id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        music=_build_music_items(music_files),
        announcements=_build_announcement_items(schedule_rows),
        settings=_build_settings_item(branch_with_settings),
    )


async def confirm_sync(
    branch_id: int,
    body: SyncConfirmRequest,
    db: AsyncSession,
) -> SyncConfirmResponse:
    """
    Agent sync bitirdiğinde last_sync_at ve sync_status güncelle.

    status: "ok" veya "partial" olabilir.
    """
    repo = BranchRepository(db)
    updated = await repo.update_last_sync(branch_id, sync_status=body.status)

    if not updated:
        return SyncConfirmResponse(ok=False, message="Branch bulunamadı")

    return SyncConfirmResponse(
        ok=True,
        message=f"Sync kaydedildi: {body.synced_files_count} dosya, durum={body.status}",
    )
