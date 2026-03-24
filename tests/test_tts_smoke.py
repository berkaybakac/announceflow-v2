import asyncio
import importlib.util
import os
import shutil
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.models.base import Base
from backend.models.tts import TTSJob, TTSJobStatus
from backend.repositories.media_repository import MediaRepository
from backend.repositories.tts_repository import TTSJobRepository

os.environ.pop("TORCH_FORCE_WEIGHTS_ONLY_LOAD", None)
os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"

from backend.services import tts_service

pytestmark = pytest.mark.tts_smoke


def _assert_prerequisites() -> None:
    if os.environ.get("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD") != "1":
        raise AssertionError("Smoke requires TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1")
    current = sys.version_info[:2]
    if current != tts_service.SUPPORTED_TTS_PYTHON:
        raise AssertionError(
            f"Smoke requires Python {tts_service.SUPPORTED_TTS_PYTHON[0]}.{tts_service.SUPPORTED_TTS_PYTHON[1]}, "
            f"current={current[0]}.{current[1]}"
        )
    if importlib.util.find_spec("TTS") is None:
        raise AssertionError("Smoke requires Coqui TTS package (module 'TTS') installed")
    try:
        from transformers import BeamSearchScorer  # noqa: F401
    except (ImportError, AttributeError) as exc:
        raise AssertionError(
            "Smoke requires a transformers version exporting BeamSearchScorer"
        ) from exc
    if shutil.which("ffmpeg") is None:
        raise AssertionError("Smoke requires ffmpeg executable in PATH")
    if shutil.which("ffprobe") is None:
        raise AssertionError("Smoke requires ffprobe executable in PATH")


@pytest_asyncio.fixture
async def smoke_session_factory(
    tmp_path: Path,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    db_path = tmp_path / "smoke.db"
    database_url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(database_url, echo=False, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield session_factory
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


async def _create_job(
    session_factory: async_sessionmaker[AsyncSession],
    text: str,
    language: str = "tr",
    voice_profile: str = "tok_erkek_1",
) -> int:
    async with session_factory() as session:
        repo = TTSJobRepository(session)
        job = TTSJob(text_input=text, language=language, voice_profile=voice_profile)
        job = await repo.create(job)
        await session.commit()
        await session.refresh(job)
        return job.id


async def _get_job(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: int,
) -> TTSJob | None:
    async with session_factory() as session:
        repo = TTSJobRepository(session)
        return await repo.get_by_id(job_id)


@pytest.mark.asyncio
async def test_tts_smoke_happy_path_done_with_artifact_and_hash(
    smoke_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _assert_prerequisites()

    job_id = await _create_job(
        smoke_session_factory,
        "Merhaba, bu bir smoke test anonsudur.",
        voice_profile="tok_erkek_1",
    )
    await tts_service.process_tts_job(job_id, session_factory=smoke_session_factory)

    job = await _get_job(smoke_session_factory, job_id)
    assert job is not None
    assert job.status == TTSJobStatus.DONE
    assert job.media_id is not None
    assert job.output_path is not None

    output_path = Path(job.output_path)
    assert await asyncio.to_thread(output_path.exists)

    async with smoke_session_factory() as session:
        media_repo = MediaRepository(session)
        media = await media_repo.get_by_id(job.media_id)
        assert media is not None
        assert bool(media.file_hash)


@pytest.mark.asyncio
async def test_tts_smoke_fail_path_marks_failed(
    smoke_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _assert_prerequisites()

    job_id = await _create_job(
        smoke_session_factory,
        "Bu iş bilinçli olarak fail edilmeli.",
        language="zz-invalid",
    )
    await tts_service.process_tts_job(job_id, session_factory=smoke_session_factory)

    job = await _get_job(smoke_session_factory, job_id)
    assert job is not None
    assert job.status == TTSJobStatus.FAILED
    assert job.processed_at is not None
