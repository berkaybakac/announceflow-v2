import asyncio
import logging
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.core.database import async_session_factory
from backend.core.settings import settings
from backend.models.media import MediaFile, MediaType
from backend.models.tts import TTSJobStatus
from backend.repositories.media_repository import MediaRepository
from backend.repositories.tts_repository import TTSJobRepository
from backend.services import media_service
from backend.services.voice_profile_resolver import (
    VoiceProfileResolutionError,
    resolve_builtin_speaker,
)

logger = logging.getLogger(__name__)
SUPPORTED_TTS_PYTHON = (3, 11)

# ---------------------------------------------------------------------------
# Singleton TTS Model (Lazy Loading)
# ---------------------------------------------------------------------------
_tts_model: "TTS | None" = None  # type: ignore[name-defined]
_model_lock = threading.Lock()
_inference_lock = threading.Lock()


def _ensure_numba_cache_dir() -> None:
    """
    Ensure numba has a writable cache directory before importing TTS/librosa.

    Some environments fail at import time if NUMBA cache cannot be resolved.
    """
    if os.environ.get("NUMBA_CACHE_DIR"):
        return
    cache_dir = Path("/tmp/announceflow-numba-cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["NUMBA_CACHE_DIR"] = str(cache_dir)


def _configure_torch_weights_policy_for_tts() -> None:
    """Force torch.load defaults compatible with Coqui checkpoints in this process."""
    os.environ.pop("TORCH_FORCE_WEIGHTS_ONLY_LOAD", None)
    os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"
    import torch  # noqa: F401


def _load_model() -> "TTS":  # type: ignore[name-defined]
    """Load Coqui XTTS v2 model. Runs in thread pool, blocking is safe here."""
    _assert_tts_runtime_supported()
    _ensure_numba_cache_dir()
    _configure_torch_weights_policy_for_tts()
    if settings.COQUI_TOS_AGREED:
        os.environ["COQUI_TOS_AGREED"] = "1"
    from TTS.api import TTS  # type: ignore[import-untyped]  # noqa: N811

    model = TTS(
        model_name=settings.TTS_MODEL_NAME,
        progress_bar=False,
    )
    logger.info("TTS model loaded", extra={"model": settings.TTS_MODEL_NAME})
    return model


def _assert_tts_runtime_supported() -> None:
    current = sys.version_info[:2]
    if current != SUPPORTED_TTS_PYTHON:
        raise RuntimeError(
            f"TTS runtime requires Python {SUPPORTED_TTS_PYTHON[0]}.{SUPPORTED_TTS_PYTHON[1]}. "
            f"Current: {current[0]}.{current[1]}"
        )


def _get_or_load_model_sync() -> "TTS":  # type: ignore[name-defined]
    global _tts_model
    if _tts_model is None:
        with _model_lock:
            if _tts_model is None:
                _tts_model = _load_model()
    return _tts_model


async def get_model() -> "TTS":  # type: ignore[name-defined]
    """Thread-safe lazy singleton for TTS model."""
    return await asyncio.to_thread(_get_or_load_model_sync)


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------
def _synthesize_to_file(
    model: "TTS",  # type: ignore[name-defined]
    text: str,
    language: str,
    speaker: str,
    output_path: str,
) -> str:
    """Run TTS inference. Blocking and must be called via asyncio.to_thread."""
    model.tts_to_file(
        text=text,
        language=language,
        speaker=speaker,
        file_path=output_path,
    )
    return output_path


def _synthesize_locked(
    model: "TTS",  # type: ignore[name-defined]
    text: str,
    language: str,
    speaker: str,
    output_path: str,
) -> str:
    with _inference_lock:
        return _synthesize_to_file(model, text, language, speaker, output_path)


async def synthesize(
    text: str,
    language: str,
    voice_profile: str,
    job_id: int,
) -> Path:
    """Generate WAV from text using XTTS v2. Serialized with a thread lock."""
    model = await get_model()
    try:
        speaker = resolve_builtin_speaker(voice_profile, model)
        logger.info(
            "tts.voice_profile.resolve.ok",
            extra={
                "job_id": job_id,
                "voice_profile": voice_profile,
                "speaker_id": speaker,
            },
        )
    except VoiceProfileResolutionError as exc:
        logger.error(
            "tts.voice_profile.resolve.failed",
            extra={
                "job_id": job_id,
                "voice_profile": voice_profile,
                "reason_code": exc.reason_code,
                "registry_path": exc.registry_path,
            },
        )
        raise

    temp_dir = Path(settings.MEDIA_TEMP_PATH) / str(uuid.uuid4())
    await asyncio.to_thread(temp_dir.mkdir, parents=True, exist_ok=True)
    wav_path = temp_dir / "tts_output.wav"

    await asyncio.to_thread(
        _synthesize_locked,
        model,
        text,
        language,
        speaker,
        str(wav_path),
    )
    return wav_path


# ---------------------------------------------------------------------------
# Background Task Orchestrator
# ---------------------------------------------------------------------------
async def _mark_job_failed_with_fresh_session(
    job_id: int,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as failed_session:
        try:
            repo = TTSJobRepository(failed_session)
            job = await repo.get_by_id(job_id)
            if job is None:
                return
            job.status = TTSJobStatus.FAILED
            if job.processed_at is None:
                job.processed_at = datetime.now(timezone.utc)
            await failed_session.commit()
        except Exception:
            await failed_session.rollback()


async def process_tts_job(
    job_id: int,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Background task: synthesize text, normalize output and update DB state."""
    sf = session_factory or async_session_factory
    async with sf() as session:
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
                wav_path = await synthesize(
                    job.text_input,
                    job.language,
                    job.voice_profile,
                    job.id,
                )
            except Exception:
                job.status = TTSJobStatus.FAILED
                job.processed_at = datetime.now(timezone.utc)
                await session.commit()
                logger.exception(
                    "TTS synthesis failed",
                    extra={"job_id": job_id},
                )
                return

            # 3. Create MediaFile placeholder
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

            # 4. Normalize WAV to MP3
            final_output = Path(settings.MEDIA_STORAGE_PATH) / f"{media.id}.mp3"
            await media_service.normalize_audio(
                wav_path,
                final_output,
                media.id,
                session_factory=sf,
            )

            # 5. Refresh media with normalize_audio updates
            await session.refresh(media)

            # 6. Verify output before marking done
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

            # 7. Mark job done
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
            await _mark_job_failed_with_fresh_session(job_id, sf)
            logger.exception(
                "TTS job processing failed",
                extra={"job_id": job_id},
            )
