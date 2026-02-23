from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.log import LogEntry
from backend.repositories.base import BaseRepository


class LogRepository(BaseRepository[LogEntry]):
    """Log kayıtları için veri erişim katmanı."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LogEntry)

    async def create_batch(self, entries: list[LogEntry]) -> list[LogEntry]:
        """Toplu log kaydı oluşturur. Tek flush ile performans kazanımı."""
        self.session.add_all(entries)
        await self.session.flush()
        return entries

    async def get_by_branch(
        self,
        branch_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[LogEntry]:
        """Belirli bir şubeye ait logları yeniden eskiye sıralı getirir."""
        stmt = (
            select(LogEntry)
            .where(LogEntry.branch_id == branch_id)
            .order_by(LogEntry.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
