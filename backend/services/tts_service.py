import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.core.database import async_session_factory
from backend.core.settings import settings
from backend.models.media import MediaFile, MediaType
from backend.models.tts import TTSJobStatus
from backend.repositories.media_repository import MediaRepository
from backend.repositories.tts_repository import TTSJobRepository
from backend.services import media_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton TTS Model (Lazy Loading)
# ---------------------------------------------------------------------------
_tts_model: "TTS | None" = None  # type: ignore[name-defined]
_model_lock = asyncio.Lock()
_inference_semaphore = asyncio.Semaphore(1)


def _load_model() -> "TTS":  # type: ignore[name-defined]
    """Load Coqui XTTS v2 model. Runs in thread pool — blocking is OK here."""
    from TTS.api import TTS  # noqa: N811

    model = TTS(
        model_name=settings.TTS_MODEL_NAME,
        progress_bar=False,
    )
    logger.info("TTS model loaded", extra={"model": settings.TTS_MODEL_NAME})
    return model


async def get_model() -> "TTS":  # type: ignore[name-defined]
    """Thread-safe lazy singleton for TTS model."""
    global _tts_model
    if _tts_model is None:
        async with _model_lock:
            if _tts_model is None:
                _tts_model = await asyncio.to_thread(_load_model)
    return _tts_model


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------
def _synthesize_to_file(
    model: "TTS",  # type: ignore[name-defined]
    text: str,
    language: str,
    output_path: str,
) -> str:
    """Run TTS inference. Blocking — must be called via asyncio.to_thread."""
    model.tts_to_file(
        text=text,
        language=language,
        file_path=output_path,
    )
    return output_path


async def synthesize(text: str, language: str) -> Path:
    """Generate WAV from text using XTTS v2. Serialized via semaphore."""
    model = await get_model()

    temp_dir = Path(settings.MEDIA_TEMP_PATH) / str(uuid.uuid4())
    await asyncio.to_thread(temp_dir.mkdir, parents=True, exist_ok=True)
    wav_path = temp_dir / "tts_output.wav"

    async with _inference_semaphore:
        await asyncio.to_thread(
            _synthesize_to_file, model, text, language, str(wav_path)
        )

    return wav_path


# ---------------------------------------------------------------------------
# Background Task Orchestrator
# ---------------------------------------------------------------------------
async def process_tts_job(job_id: int) -> None:
    """Background task: synthesize text → normalize → update DB.

    Opens its own DB session — request session is already closed
    when BackgroundTasks runs.
    """
    async with async_session_factory() as session:
        try:
            tts_repo = TTSJobRepository(session)
            media_repo = MediaRepository(session)
            job = await tts_repo.get_by_id(job_id)
            if job is None:
                logger.error("TTS job not found", extra={"job_id": job_id})
                return

            # 1. Mark as processing
            job.status = TTSJobStatus.PROCESSING
            await session.commit()

            # 2. Synthesize WAV
            try:
                wav_path = await synthesize(job.text_input, job.language)
            except Exception:
                job.status = TTSJobStatus.FAILED
                job.processed_at = datetime.now(timezone.utc)
                await session.commit()
                logger.exception(
                    "TTS synthesis failed",
                    extra={"job_id": job_id},
                )
                return

            # 3. Create MediaFile record (placeholder — normalize_audio updates it)
            file_name = job.text_input[:50].strip() + ".mp3"
            media = MediaFile(
                file_name=file_name,
                file_path=str(wav_path),
                file_hash="",
                type=MediaType.ANONS,
                duration=0,
                size_bytes=0,
            )
            media = await media_repo.create(media)
            await session.commit()

            # 4. Normalize WAV → MP3 (reuse existing pipeline)
            final_output = Path(settings.MEDIA_STORAGE_PATH) / f"{media.id}.mp3"
            await media_service.normalize_audio(wav_path, final_output, media.id)

            # 5. Refresh media to get updated fields from normalize_audio
            await session.refresh(media)

            # 6. Verify normalization output before marking job done
            output_exists = await asyncio.to_thread(final_output.exists)
            if not output_exists or not media.file_hash:
                job.status = TTSJobStatus.FAILED
                job.processed_at = datetime.now(timezone.utc)
                await session.commit()
                logger.error(
                    "TTS normalization failed",
                    extra={"job_id": job_id, "media_id": media.id},
                )
                return

            # 7. Mark job as done
            job.status = TTSJobStatus.DONE
            job.media_id = media.id
            job.output_path = str(final_output)
            job.processed_at = datetime.now(timezone.utc)
            await session.commit()

            logger.info(
                "TTS job completed",
                extra={"job_id": job_id, "media_id": media.id},
            )

        except Exception:
            await session.rollback()
            # Try to mark as failed
            try:
                job = await tts_repo.get_by_id(job_id)
                if job and job.status != TTSJobStatus.FAILED:
                    job.status = TTSJobStatus.FAILED
                    job.processed_at = datetime.now(timezone.utc)
                    await session.commit()
            except Exception:
                pass
            logger.exception(
                "TTS job processing failed",
                extra={"job_id": job_id},
            )
