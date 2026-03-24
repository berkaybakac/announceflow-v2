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
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.settings import settings
from backend.dependencies import get_current_device, get_current_user
from backend.models.branch import Branch
from backend.models.media import MediaFile, MediaType
from backend.models.tts import TTSJob  # noqa: F811
from backend.models.user import User
from backend.repositories.media_repository import MediaRepository
from backend.repositories.tts_repository import TTSJobRepository
from backend.schemas.media import MediaUploadResponse
from backend.schemas.tts import TTSJobRead, TTSRequest
from backend.services import media_service, tts_service

router = APIRouter(prefix="/api/v1/media", tags=["media"])


def _parse_media_type(media_type: str) -> MediaType:
    try:
        return MediaType(media_type.upper())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Geçersiz media_type. Kabul edilen: {[e.value for e in MediaType]}",
        ) from exc


async def _save_upload_or_raise(file: UploadFile) -> Path:
    try:
        return await media_service.save_upload_to_temp(file)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc


async def _cleanup_temp_path(temp_path: Path) -> None:
    await asyncio.to_thread(shutil.rmtree, temp_path.parent, True)


async def _validate_uploaded_audio(temp_path: Path) -> dict:
    probe = await media_service.probe_audio(temp_path)
    if probe["has_audio"]:
        return probe
    await _cleanup_temp_path(temp_path)
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="Yüklenen dosya geçerli bir ses akışı içermiyor.",
    )


async def _check_duplicate_or_raise(repo: MediaRepository, temp_path: Path) -> str:
    pre_hash = await asyncio.to_thread(media_service.compute_sha256, temp_path)
    existing = await repo.get_by_hash(pre_hash)
    if existing is None:
        return pre_hash
    await _cleanup_temp_path(temp_path)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Aynı dosya zaten mevcut: media_id={existing.id}",
    )


async def _create_placeholder_media(
    repo: MediaRepository,
    file: UploadFile,
    media_type: MediaType,
    temp_path: Path,
    pre_hash: str,
    duration_seconds: int,
) -> MediaFile:
    media = MediaFile(
        file_name=file.filename or "upload.mp3",
        file_path=str(temp_path),
        file_hash=pre_hash,
        type=media_type,
        duration=duration_seconds,
        size_bytes=0,
    )
    return await repo.create(media)


def _enqueue_normalization(
    background_tasks: BackgroundTasks,
    temp_path: Path,
    media_id: int,
) -> None:
    final_output = Path(settings.MEDIA_STORAGE_PATH) / f"{media_id}.mp3"
    background_tasks.add_task(
        media_service.normalize_audio,
        temp_path,
        final_output,
        media_id,
    )


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
    repo = MediaRepository(db)
    media_type_enum = _parse_media_type(media_type)
    temp_path = await _save_upload_or_raise(file)
    probe = await _validate_uploaded_audio(temp_path)
    pre_hash = await _check_duplicate_or_raise(repo, temp_path)
    media = await _create_placeholder_media(
        repo=repo,
        file=file,
        media_type=media_type_enum,
        temp_path=temp_path,
        pre_hash=pre_hash,
        duration_seconds=probe["duration_seconds"],
    )
    _enqueue_normalization(background_tasks, temp_path, media.id)

    return MediaUploadResponse(
        media_id=media.id,
        file_name=media.file_name,
        status="processing",
        message="Dosya alındı, normalizasyon kuyruğunda.",
    )


@router.get("/{media_id}/download")
async def download_media(
    media_id: int,
    db: AsyncSession = Depends(get_db),
    current_device: Branch = Depends(get_current_device),
) -> FileResponse:
    repo = MediaRepository(db)
    media = await repo.get_by_id(media_id)
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medya bulunamadı.",
        )

    has_access = await repo.is_accessible_for_branch(
        media_id=media_id,
        branch_id=current_device.id,
        group_tag=current_device.group_tag,
    )
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu medya için erişim yetkiniz yok.",
        )

    file_path = Path(media.file_path)
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medya dosyası bulunamadı.",
        )

    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        filename=media.file_name,
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
