from collections.abc import AsyncGenerator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.settings import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=5,
)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency. Yield session, auto-commit/rollback."""
    async with async_session_factory() as session:
        completed_without_error = False
        try:
            yield session
            completed_without_error = True
        finally:
            if completed_without_error:
                try:
                    await session.commit()
                except SQLAlchemyError:
                    await session.rollback()
                    raise
            elif session.in_transaction():
                await session.rollback()
