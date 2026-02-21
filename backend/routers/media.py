import asyncio
import shutil
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.settings import settings
from backend.dependencies import get_current_user
from backend.models.media import MediaFile, MediaType
from backend.models.tts import TTSJob  # noqa: F811
from backend.models.user import User
from backend.repositories.media_repository import MediaRepository
from backend.repositories.tts_repository import TTSJobRepository
from backend.schemas.media import MediaUploadResponse
from backend.schemas.tts import TTSJobRead, TTSRequest
from backend.services import media_service, tts_service

router = APIRouter(prefix="/api/v1/media", tags=["media"])


@router.post(
    "/upload",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_media(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    media_type: str = Form(default="MUSIC"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MediaUploadResponse:
    # 1. Validate media_type enum
    try:
        media_type_enum = MediaType(media_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Geçersiz media_type. Kabul edilen: {[e.value for e in MediaType]}",
        )

    # 2. Stream to temp disk
    try:
        temp_path = await media_service.save_upload_to_temp(file)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        )

    # 3. Validate audio via ffprobe
    probe = await media_service.probe_audio(temp_path)
    if not probe["has_audio"]:
        await asyncio.to_thread(shutil.rmtree, temp_path.parent, True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Yüklenen dosya geçerli bir ses akışı içermiyor.",
        )

    # 4. Duplicate check via SHA256
    pre_hash = await asyncio.to_thread(media_service.compute_sha256, temp_path)
    repo = MediaRepository(db)
    existing = await repo.get_by_hash(pre_hash)
    if existing:
        await asyncio.to_thread(shutil.rmtree, temp_path.parent, True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Aynı dosya zaten mevcut: media_id={existing.id}",
        )

    # 5. Create DB record (placeholder — updated by background task)
    media = MediaFile(
        file_name=file.filename or "upload.mp3",
        file_path=str(temp_path),
        file_hash=pre_hash,
        type=media_type_enum,
        duration=probe["duration_seconds"],
        size_bytes=0,
    )
    media = await repo.create(media)

    # 6. Schedule FFmpeg normalization
    final_output = Path(settings.MEDIA_STORAGE_PATH) / f"{media.id}.mp3"
    background_tasks.add_task(
        media_service.normalize_audio,
        temp_path,
        final_output,
        media.id,
    )

    return MediaUploadResponse(
        media_id=media.id,
        file_name=media.file_name,
        status="processing",
        message="Dosya alındı, normalizasyon kuyruğunda.",
    )


# ---------------------------------------------------------------------------
# TTS Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/tts",
    response_model=TTSJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_tts_job(
    background_tasks: BackgroundTasks,
    body: TTSRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TTSJobRead:
    # 1. Create TTS job record
    job = TTSJob(
        text_input=body.text,
        language=body.language,
        voice_profile=body.voice_profile,
    )
    repo = TTSJobRepository(db)
    job = await repo.create(job)
    await db.commit()
    await db.refresh(job)

    # 2. Schedule background processing
    background_tasks.add_task(tts_service.process_tts_job, job.id)

    return TTSJobRead.model_validate(job)


@router.get(
    "/tts/{job_id}",
    response_model=TTSJobRead,
)
async def get_tts_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TTSJobRead:
    repo = TTSJobRepository(db)
    job = await repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TTS job bulunamadı.",
        )
    return TTSJobRead.model_validate(job)
