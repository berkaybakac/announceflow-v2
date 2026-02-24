"""Schedule yönetimi REST API — YALNIZCA ADMIN.

Endpoint'ler:
- POST   /api/v1/schedules/check-conflict  → Ön çakışma kontrolü
- POST   /api/v1/schedules/                → Yeni schedule oluşturma
- GET    /api/v1/schedules/                → Paginated listeleme
- PUT    /api/v1/schedules/{schedule_id}   → Güncelleme
- DELETE /api/v1/schedules/{schedule_id}   → Silme

Guard: Tüm endpoint'ler verify_vendor_admin ile korunur.
Cihaz JWT'leri (device token) bu endpoint'lere ERİŞEMEZ.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.dependencies import verify_vendor_admin
from backend.models.user import User
from backend.schemas.schedule import (
    ConflictCheckRequest,
    ConflictCheckResponse,
    PaginatedScheduleResponse,
    ScheduleCreate,
    ScheduleRead,
    ScheduleUpdate,
)
from backend.services import schedule_service

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


@router.post(
    "/check-conflict",
    response_model=ConflictCheckResponse,
)
async def check_conflict(
    body: ConflictCheckRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(verify_vendor_admin),
) -> ConflictCheckResponse:
    """Yükleme öncesi çakışma taraması."""
    return await schedule_service.check_conflict(db, body)


@router.post(
    "/",
    response_model=ScheduleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule(
    body: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(verify_vendor_admin),
) -> ScheduleRead:
    """Yeni schedule oluşturur."""
    return await schedule_service.create_schedule(db, body)


@router.get(
    "/",
    response_model=PaginatedScheduleResponse,
)
async def list_schedules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(verify_vendor_admin),
) -> PaginatedScheduleResponse:
    """Dashboard için paginated schedule listesi."""
    return await schedule_service.list_schedules(db, page, page_size)


@router.put(
    "/{schedule_id}",
    response_model=ScheduleRead,
)
async def update_schedule(
    schedule_id: int,
    body: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(verify_vendor_admin),
) -> ScheduleRead:
    """Mevcut schedule'ı günceller."""
    return await schedule_service.update_schedule(db, schedule_id, body)


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(verify_vendor_admin),
) -> None:
    """Schedule siler."""
    await schedule_service.delete_schedule(db, schedule_id)
