"""Scheduler CRUD ve çakışma motoru iş mantığı katmanı.

Sorumluluklar:
- media_id → type=ANONS guard
- end_time otomatik hesaplama (play_at + media.duration)
- Tek seferlik (play_at) çakışma kontrolü (interval overlap + target filtresi)
- CRUD orchestration
"""

import logging
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.media import MediaType
from backend.models.schedule import Schedule
from backend.repositories.media_repository import MediaRepository
from backend.repositories.schedule_repository import ScheduleRepository
from backend.schemas.schedule import (
    ConflictCheckRequest,
    ConflictCheckResponse,
    PaginatedScheduleResponse,
    ScheduleCreate,
    ScheduleRead,
    ScheduleUpdate,
)

logger = logging.getLogger(__name__)


def _to_read(schedule: Schedule, media_file_name: str, media_duration: int) -> ScheduleRead:
    """Schedule + media bilgisini ScheduleRead'e dönüştür."""
    return ScheduleRead(
        id=schedule.id,
        media_id=schedule.media_id,
        media_file_name=media_file_name,
        media_duration=media_duration,
        target_type=schedule.target_type,
        target_id=schedule.target_id,
        target_group=schedule.target_group,
        play_at=schedule.play_at,
        cron_expression=schedule.cron_expression,
        end_time=schedule.end_time,
        is_active=schedule.is_active,
        created_at=schedule.created_at,
    )


async def _validate_anons_media(
    media_repo: MediaRepository, media_id: int
) -> tuple[str, int]:
    """media_id'nin ANONS tipinde olduğunu doğrular.

    Returns: (file_name, duration)
    Raises: HTTPException 422 eğer media bulunamazsa veya ANONS değilse.
    """
    media = await media_repo.get_by_id(media_id)
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"media_id={media_id} bulunamadı.",
        )
    if media.type != MediaType.ANONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"media_id={media_id} tipi '{media.type.value}'. Yalnızca ANONS tipindeki dosyalar zamanlanabilir.",
        )
    return media.file_name, media.duration


async def _check_and_raise_conflict(
    schedule_repo: ScheduleRepository,
    media_repo: MediaRepository,
    play_at: datetime,
    duration: int,
    target_type: str,
    target_id: int | None,
    target_group: str | None,
    exclude_id: int | None = None,
) -> None:
    """Çakışma varsa HTTP 409 fırlatır."""
    end_time = play_at + timedelta(seconds=duration)
    result = await schedule_repo.find_overlapping_one_time(
        play_at=play_at,
        end_time=end_time,
        target_type=target_type,
        target_id=target_id,
        target_group=target_group,
        exclude_id=exclude_id,
    )
    if result is not None:
        conflict_schedule, conflict_media = result
        conflict_read = _to_read(
            conflict_schedule, conflict_media.file_name, conflict_media.duration
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Seçtiğiniz zaman diliminde çakışan bir zamanlama mevcut.",
                "conflicting_schedule": conflict_read.model_dump(mode="json"),
            },
        )


# ── CRUD Operations ─────────────────────────────────────────────


async def create_schedule(
    db: AsyncSession, data: ScheduleCreate
) -> ScheduleRead:
    """Yeni schedule oluşturur. ANONS guard + çakışma kontrolü uygular."""
    media_repo = MediaRepository(db)
    schedule_repo = ScheduleRepository(db)

    # 1. ANONS guard
    file_name, duration = await _validate_anons_media(media_repo, data.media_id)

    # 2. end_time hesapla (sadece play_at varsa)
    end_time = None
    if data.play_at is not None:
        end_time = data.play_at + timedelta(seconds=duration)

        # 3. Çakışma kontrolü
        await _check_and_raise_conflict(
            schedule_repo,
            media_repo,
            play_at=data.play_at,
            duration=duration,
            target_type=data.target_type,
            target_id=data.target_id,
            target_group=data.target_group,
        )

    # 4. DB insert
    schedule = Schedule(
        media_id=data.media_id,
        target_type=data.target_type,
        target_id=data.target_id,
        target_group=data.target_group,
        play_at=data.play_at,
        cron_expression=data.cron_expression,
        end_time=end_time,
        is_active=data.is_active,
    )
    schedule = await schedule_repo.create(schedule)
    await db.commit()
    await db.refresh(schedule)

    logger.info(
        "Schedule created",
        extra={"schedule_id": schedule.id, "media_id": data.media_id},
    )
    return _to_read(schedule, file_name, duration)


async def update_schedule(
    db: AsyncSession, schedule_id: int, data: ScheduleUpdate
) -> ScheduleRead:
    """Mevcut schedule'ı günceller."""
    schedule_repo = ScheduleRepository(db)
    media_repo = MediaRepository(db)

    # 1. Var mı?
    existing = await schedule_repo.get_by_id(schedule_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule id={schedule_id} bulunamadı.",
        )

    # Güncellenecek alanları belirle
    update_fields = data.model_dump(exclude_unset=True, exclude={"_play_at_set", "_cron_set"})

    # 2. media_id değiştiyse ANONS guard
    new_media_id = update_fields.get("media_id", existing.media_id)
    file_name, duration = await _validate_anons_media(media_repo, new_media_id)

    # Alanları uygula
    for field, value in update_fields.items():
        setattr(existing, field, value)

    # XOR bütünlük kontrolü (Son durumda)
    if existing.play_at is not None and existing.cron_expression is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="play_at ve cron_expression aynı anda dolu olamaz (XOR ihlali).",
        )
    if existing.play_at is None and existing.cron_expression is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="play_at ve cron_expression aynı anda boş olamaz (XOR ihlali).",
        )

    # 3. end_time yeniden hesapla
    if existing.play_at is not None:
        existing.end_time = existing.play_at + timedelta(seconds=duration)

        # 4. Çakışma kontrolü (kendini hariç tut)
        await _check_and_raise_conflict(
            schedule_repo,
            media_repo,
            play_at=existing.play_at,
            duration=duration,
            target_type=existing.target_type,
            target_id=existing.target_id,
            target_group=existing.target_group,
            exclude_id=schedule_id,
        )
    else:
        existing.end_time = None

    await db.commit()
    await db.refresh(existing)

    logger.info(
        "Schedule updated",
        extra={"schedule_id": schedule_id},
    )
    return _to_read(existing, file_name, duration)


async def delete_schedule(db: AsyncSession, schedule_id: int) -> None:
    """Schedule siler."""
    schedule_repo = ScheduleRepository(db)

    existing = await schedule_repo.get_by_id(schedule_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule id={schedule_id} bulunamadı.",
        )

    await schedule_repo.delete(existing)
    await db.commit()

    logger.info("Schedule deleted", extra={"schedule_id": schedule_id})


async def list_schedules(
    db: AsyncSession, page: int = 1, page_size: int = 20
) -> PaginatedScheduleResponse:
    """Paginated schedule listesi döndürür (media JOIN ile)."""
    schedule_repo = ScheduleRepository(db)

    rows, total = await schedule_repo.get_all_paginated(page, page_size)

    items = [
        _to_read(schedule, media.file_name, media.duration)
        for schedule, media in rows
    ]

    return PaginatedScheduleResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


async def check_conflict(
    db: AsyncSession, data: ConflictCheckRequest
) -> ConflictCheckResponse:
    """Ön çakışma kontrolü (POST /check-conflict)."""
    media_repo = MediaRepository(db)
    schedule_repo = ScheduleRepository(db)

    _, duration = await _validate_anons_media(media_repo, data.media_id)

    end_time = data.play_at + timedelta(seconds=duration)
    result = await schedule_repo.find_overlapping_one_time(
        play_at=data.play_at,
        end_time=end_time,
        target_type=data.target_type,
        target_id=data.target_id,
        target_group=data.target_group,
        exclude_id=data.exclude_schedule_id,
    )

    if result is None:
        return ConflictCheckResponse(has_conflict=False)

    conflict_schedule, conflict_media = result
    return ConflictCheckResponse(
        has_conflict=True,
        conflicting_schedule=_to_read(
            conflict_schedule, conflict_media.file_name, conflict_media.duration
        ),
    )
