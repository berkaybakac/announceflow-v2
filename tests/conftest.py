import os
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.database import get_db
from backend.core.security import hash_password
from backend.main import app
from backend.models.base import Base
from backend.models.branch import Branch
from backend.models.user import User

_TEST_DB_DIR = Path(__file__).resolve().parent / ".tmp"
_TEST_DB_DIR.mkdir(exist_ok=True)
TEST_DATABASE_URL = ""
os.environ.setdefault("COQUI_TOS_AGREED", "1")

engine: AsyncEngine | None = None
test_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_worker_id() -> str:
    return os.getenv("PYTEST_XDIST_WORKER", "local")


@pytest_asyncio.fixture(autouse=True)
async def setup_database(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
):
    global TEST_DATABASE_URL, engine, test_session_factory

    if request.node.get_closest_marker("tts_smoke"):
        yield
        return

    run_id = uuid4().hex
    worker_id = _get_worker_id()
    db_file = tmp_path_factory.mktemp(f"db-{worker_id}") / f"test-{run_id}.db"
    TEST_DATABASE_URL = f"sqlite+aiosqlite:///{db_file}"
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    test_session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
        try:
            db_file.unlink(missing_ok=True)
        except OSError:
            pass


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    if test_session_factory is None:
        raise RuntimeError("test_session_factory is not initialized")
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    if test_session_factory is None:
        raise RuntimeError("test_session_factory is not initialized")
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        username="testuser",
        password_hash=hash_password("testpass123"),
        is_vendor_admin=False,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        username="admin",
        password_hash=hash_password("adminpass123"),
        is_vendor_admin=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_branch(db_session: AsyncSession) -> Branch:
    branch = Branch(
        name="Test Şube",
        city="Gaziantep",
        district="Şahinbey",
        token="test-device-token-uuid",
        is_active=True,
        volume_music=50,
        volume_announce=80,
    )
    db_session.add(branch)
    await db_session.commit()
    await db_session.refresh(branch)
    return branch


@pytest_asyncio.fixture
async def inactive_branch(db_session: AsyncSession) -> Branch:
    branch = Branch(
        name="Devre Dışı Şube",
        city="İstanbul",
        district="Kadıköy",
        token="inactive-device-token-uuid",
        is_active=False,
        volume_music=50,
        volume_announce=80,
    )
    db_session.add(branch)
    await db_session.commit()
    await db_session.refresh(branch)
    return branch


@pytest.fixture(autouse=True)
def override_media_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.core.settings.settings.MEDIA_STORAGE_PATH",
        str(tmp_path / "media"),
    )
    monkeypatch.setattr(
        "backend.core.settings.settings.MEDIA_TEMP_PATH",
        str(tmp_path / "temp"),
    )


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
