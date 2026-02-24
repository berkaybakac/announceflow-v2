"""
Manifest Service — Sync Engine (Backend).

Branch'e ait müzik, anons ve ayar bilgilerini tek manifest JSON olarak derler.
Agent'ın sync onayını kaydeder.
"""

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import TypeVar

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
ItemT = TypeVar("ItemT")


def _truncate_for_ram_safety(
    branch_id: int,
    items: Sequence[ItemT],
    max_files: int,
    item_type: str,
) -> list[ItemT]:
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


async def build_manifest(branch: Branch, db: AsyncSession) -> ManifestResponse:
    """
    Branch için tam manifest oluştur.

    3 sorgu çalıştırır:
    1. Müzikler — media_targets ACL (ALL ∪ BRANCH ∪ GROUP)
    2. Anonslar — schedules ACL (ALL ∪ BRANCH ∪ GROUP) + media JOIN
    3. Settings — branch_settings 1-to-1

    Hash/size hesaplaması YAPILMAZ — DB'den hazır okunur.
    """
    media_repo = MediaRepository(db)
    schedule_repo = ScheduleRepository(db)
    branch_repo = BranchRepository(db)
    max_files = settings.MANIFEST_MAX_FILES
    fetch_limit = max_files + 1

    # 1. Müzikler (ACL-aware, DISTINCT)
    music_files = await media_repo.get_music_for_branch(
        branch.id,
        branch.group_tag,
        limit=fetch_limit,
    )
    music_files = _truncate_for_ram_safety(
        branch.id,
        music_files,
        max_files,
        "music",
    )

    # 2. Anonslar + Medya (ACL-aware, JOIN)
    schedule_rows = await schedule_repo.get_schedules_for_branch_with_media(
        branch.id,
        branch.group_tag,
        limit=fetch_limit,
    )
    schedule_rows = _truncate_for_ram_safety(
        branch.id,
        schedule_rows,
        max_files,
        "announcements",
    )

    # 3. Settings (eager load)
    branch_with_settings = await branch_repo.get_with_settings(branch.id)

    # --- Build music items ---
    music_items = [
        ManifestMediaItem(
            id=mf.id,
            file_name=mf.file_name,
            file_hash=mf.file_hash,
            type=mf.type.value,
            size_bytes=mf.size_bytes,
            download_url=f"/api/v1/media/download/{mf.id}",
        )
        for mf in music_files
    ]

    # --- Build announcement items ---
    announcement_items = [
        ManifestScheduleItem(
            id=sched.id,
            media_id=media.id,
            media_file_name=media.file_name,
            media_file_hash=media.file_hash,
            media_size_bytes=media.size_bytes,
            media_download_url=f"/api/v1/media/download/{media.id}",
            play_at=sched.play_at,
            cron_expression=sched.cron_expression,
            end_time=sched.end_time,
        )
        for sched, media in schedule_rows
    ]

    # --- Build settings (strftime type safety) ---
    settings_item = None
    if (
        branch_with_settings is not None
        and branch_with_settings.settings is not None
    ):
        bs = branch_with_settings.settings
        settings_item = ManifestSettingsItem(
            work_start=bs.work_start.strftime("%H:%M"),
            work_end=bs.work_end.strftime("%H:%M"),
            volume_music=branch_with_settings.volume_music,
            volume_announce=branch_with_settings.volume_announce,
            loop_mode=bs.loop_mode,
        )

    return ManifestResponse(
        branch_id=branch.id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        music=music_items,
        announcements=announcement_items,
        settings=settings_item,
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
