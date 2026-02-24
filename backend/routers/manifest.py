"""
Manifest Router — Sync Engine Endpoint'leri.

- GET  /api/v1/manifest/{branch_id}  → Manifest JSON döner (Device JWT only)
- POST /api/v1/agent/sync_confirm    → Sync onayı kaydeder (Device JWT only)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.dependencies import get_current_device
from backend.models.branch import Branch
from backend.schemas.manifest import (
    ManifestResponse,
    SyncConfirmRequest,
    SyncConfirmResponse,
)
from backend.services.manifest_service import build_manifest, confirm_sync

router = APIRouter(prefix="/api/v1", tags=["sync"])


@router.get("/manifest/{branch_id}", response_model=ManifestResponse)
async def get_manifest(
    branch_id: int,
    branch: Branch = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> ManifestResponse:
    """
    Branch'e ait müzik, anons ve ayar manifest'ini döner.

    Güvenlik:
    - Sadece Device JWT kabul eder (Admin JWT → 401)
    - URL'deki branch_id ile token'daki branch_id eşleşmeli (→ 403)
    """
    if branch.id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu manifest'e erişim yetkiniz yok",
        )
    return await build_manifest(branch, db)


@router.post("/agent/sync_confirm", response_model=SyncConfirmResponse)
async def sync_confirm_endpoint(
    body: SyncConfirmRequest,
    branch: Branch = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> SyncConfirmResponse:
    """
    Agent sync bitirdiğinde bildirir.

    DB'de branch'in last_sync_at ve sync_status alanlarını günceller.
    """
    return await confirm_sync(branch.id, body, db)
