from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.dependencies import get_current_device
from backend.models.branch import Branch
from backend.repositories.log_repository import LogRepository
from backend.schemas.log import LogBatchCreate
from backend.services.log_service import LogService

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


@router.post("/", status_code=201)
async def ingest_logs(
    payload: LogBatchCreate,
    branch: Branch = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """
    Şube cihazından gelen log kayıtlarını toplu olarak alır.

    - **Auth:** Sadece device JWT (şube token'ı) ile erişilebilir.
    - **Flood Protection:** Aynı mesaj saniyede >10 kez gelirse sessizce atılır.
    - **Batch limit:** Tek istekte maksimum 100 log kaydı.
    """
    repo = LogRepository(db)
    service = LogService(repo)
    accepted = await service.ingest(branch.id, payload.logs)
    return {"accepted": accepted}
