import asyncio
import hashlib
import json
import logging
import shutil
import uuid
from pathlib import Path

import aiofiles
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.core.database import async_session_factory
from backend.core.settings import settings
from backend.repositories.media_repository import MediaRepository

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1MB


async def save_upload_to_temp(file: UploadFile) -> Path:
    """Stream uploaded file to disk in 1MB chunks. Never loads full file into RAM."""
    temp_dir = Path(settings.MEDIA_TEMP_PATH) / str(uuid.uuid4())
    await asyncio.to_thread(temp_dir.mkdir, parents=True, exist_ok=True)

    raw_name = file.filename or "upload"
    normalized_name = raw_name.replace("\\", "/")
    parsed_name = Path(normalized_name)
    if ".." in parsed_name.parts:
        raise ValueError("Geçersiz dosya adı")
    safe_name = parsed_name.name
    if safe_name in {"", ".", ".."}:
        raise ValueError("Geçersiz dosya adı")

    dest = temp_dir / safe_name

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    written = 0

    async with aiofiles.open(dest, "wb") as f:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                await asyncio.to_thread(dest.unlink, missing_ok=True)
                await asyncio.to_thread(shutil.rmtree, temp_dir, True)
                raise ValueError(
                    f"Dosya maksimum boyutu aşıyor: {settings.MAX_UPLOAD_SIZE_MB}MB"
                )
            await f.write(chunk)

    return dest


async def probe_audio(path: Path) -> dict:
    """Validate audio file via ffprobe and extract duration."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name:format=duration",
            "-of", "json",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return {"has_audio": False, "duration_seconds": 0}
    stdout, _ = await proc.communicate()

    if proc.returncode != 0:
        return {"has_audio": False, "duration_seconds": 0}

    try:
        data = json.loads(stdout.decode())
    except json.JSONDecodeError:
        return {"has_audio": False, "duration_seconds": 0}
    streams = data.get("streams", [])
    has_audio = bool(streams)

    duration_raw = data.get("format", {}).get("duration", "0")
    try:
        duration = int(float(duration_raw))
    except (ValueError, TypeError):
        duration = 0

    return {"has_audio": has_audio, "duration_seconds": duration}


def compute_sha256(path: Path) -> str:
    """Compute SHA256 hash in 64KB blocks."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


async def normalize_audio(
    temp_path: Path,
    output_path: Path,
    media_id: int,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Background task: FFmpeg -14 LUFS normalization (EBU R128).

    Opens its own DB session — request session is already closed
    when BackgroundTasks runs.
    """
    await asyncio.to_thread(output_path.parent.mkdir, parents=True, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i", str(temp_path),
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-ar", "44100",
        "-ab", "192k",
        str(output_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    # Clean up temp directory
    await asyncio.to_thread(shutil.rmtree, temp_path.parent, True)

    if proc.returncode != 0:
        logger.error(
            "FFmpeg normalization failed",
            extra={"media_id": media_id, "stderr": stderr.decode()[-500:]},
        )
        return

    # Compute final metadata (offload blocking I/O to thread pool)
    file_hash = await asyncio.to_thread(compute_sha256, output_path)
    stat_result = await asyncio.to_thread(output_path.stat)
    size_bytes = stat_result.st_size
    probe_result = await probe_audio(output_path)
    duration = probe_result["duration_seconds"]

    # Update DB record with own session
    sf = session_factory or async_session_factory
    async with sf() as session:
        try:
            repo = MediaRepository(session)
            media = await repo.get_by_id(media_id)
            if media:
                media.file_hash = file_hash
                media.file_path = str(output_path)
                media.duration = duration
                media.size_bytes = size_bytes
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                "Failed to update media record after normalization",
                extra={"media_id": media_id},
            )
