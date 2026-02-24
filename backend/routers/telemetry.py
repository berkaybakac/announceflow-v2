"""
Telemetri API — Dashboard anlık cihaz sağlık bilgileri.

Veri kaynağı: In-Memory TelemetryCache (DB'den okumaz).
Sadece vendor admin erişebilir (/admin/* route'ları).
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import verify_vendor_admin
from backend.models.user import User
from backend.services.telemetry_cache import telemetry_cache

router = APIRouter(
    prefix="/api/v1/admin/telemetry",
    tags=["telemetry"],
)


@router.get(
    "",
    summary="Tüm şubelerin anlık telemetri verisi",
)
async def get_all_telemetry(
    _current_user: User = Depends(verify_vendor_admin),
) -> dict[str, Any]:
    """Fleet dashboard görünümü — tüm cache'i döner."""
    return {"branches": telemetry_cache.get_all()}


@router.get(
    "/{branch_id}",
    summary="Tek şubenin anlık telemetri verisi",
)
async def get_branch_telemetry(
    branch_id: int,
    _current_user: User = Depends(verify_vendor_admin),
) -> dict[str, Any]:
    """Tek branch telemetri verisi. Cache'de yoksa 404."""
    data = telemetry_cache.get(branch_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu şubenin telemetri verisi bulunamadı",
        )
    return {"branch_id": branch_id, "telemetry": data}
