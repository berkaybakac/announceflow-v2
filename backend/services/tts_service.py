import asyncio
import logging
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
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

_SYNTHESIS_ERRORS = (
    VoiceProfileResolutionError,
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
)

_TTS_PROCESSING_ERRORS = (
    SQLAlchemyError,
    RuntimeError,
    OSError,
    ValueError,
    TypeError,
)

_MARK_FAILED_ERRORS = (SQLAlchemyError, RuntimeError)

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
def _mark_failed_in_memory(job: Any) -> None:
    job.status = TTSJobStatus.FAILED
    job.processed_at = datetime.now(timezone.utc)


def _build_placeholder_name(text_input: str) -> str:
    return text_input[:50].strip() + ".mp3"


async def _mark_failed_and_commit(session: AsyncSession, job: Any) -> None:
    _mark_failed_in_memory(job)
    await session.commit()


async def _mark_job_processing(session: AsyncSession, job: Any) -> None:
    job.status = TTSJobStatus.PROCESSING
    await session.commit()


async def _try_synthesize(job: Any, job_id: int) -> Path | None:
    try:
        return await synthesize(job.text_input, job.language, job.voice_profile, job.id)
    except asyncio.CancelledError:
        raise
    except _SYNTHESIS_ERRORS:
        logger.exception("TTS synthesis failed", extra={"job_id": job_id})
        return None


async def _create_placeholder_media(
    media_repo: MediaRepository,
    text_input: str,
    wav_path: Path,
) -> MediaFile:
    media = MediaFile(
        file_name=_build_placeholder_name(text_input),
        file_path=str(wav_path),
        file_hash="",
        type=MediaType.ANONS,
        duration=0,
        size_bytes=0,
    )
    return await media_repo.create(media)


async def _run_normalization(
    session_factory: async_sessionmaker[AsyncSession],
    wav_path: Path,
    media_id: int,
) -> Path:
    final_output = Path(settings.MEDIA_STORAGE_PATH) / f"{media_id}.mp3"
    await media_service.normalize_audio(
        wav_path,
        final_output,
        media_id,
        session_factory=session_factory,
    )
    return final_output


async def _is_output_ready(final_output: Path, media: MediaFile) -> bool:
    output_exists = await asyncio.to_thread(final_output.exists)
    return output_exists and bool(media.file_hash)


async def _mark_done(
    session: AsyncSession,
    job: Any,
    media: MediaFile,
    final_output: Path,
) -> None:
    job.status = TTSJobStatus.DONE
    job.media_id = media.id
    job.output_path = str(final_output)
    job.processed_at = datetime.now(timezone.utc)
    await session.commit()


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
        except asyncio.CancelledError:
            raise
        except _MARK_FAILED_ERRORS:
            await failed_session.rollback()


async def _process_tts_job_flow(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    job_id: int,
) -> None:
    tts_repo = TTSJobRepository(session)
    media_repo = MediaRepository(session)
    job = await tts_repo.get_by_id(job_id)
    if job is None:
        logger.error("TTS job not found", extra={"job_id": job_id})
        return

    await _mark_job_processing(session, job)

    wav_path = await _try_synthesize(job, job_id)
    if wav_path is None:
        await _mark_failed_and_commit(session, job)
        return

    media = await _create_placeholder_media(media_repo, job.text_input, wav_path)
    await session.commit()

    final_output = await _run_normalization(session_factory, wav_path, media.id)
    await session.refresh(media)
    if not await _is_output_ready(final_output, media):
        await _mark_failed_and_commit(session, job)
        logger.error("TTS normalization failed", extra={"job_id": job_id, "media_id": media.id})
        return

    await _mark_done(session, job, media, final_output)
    logger.info("TTS job completed", extra={"job_id": job_id, "media_id": media.id})


async def process_tts_job(
    job_id: int,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Background task: synthesize text, normalize output and update DB state."""
    sf = session_factory or async_session_factory
    async with sf() as session:
        try:
            await _process_tts_job_flow(session, sf, job_id)
        except asyncio.CancelledError:
            await session.rollback()
            raise
        except _TTS_PROCESSING_ERRORS:
            await session.rollback()
            await _mark_job_failed_with_fresh_session(job_id, sf)
            logger.exception("TTS job processing failed", extra={"job_id": job_id})
