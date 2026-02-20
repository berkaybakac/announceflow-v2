from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.media import TargetType
from backend.models.schedule import Schedule
from backend.repositories.base import BaseRepository


class ScheduleRepository(BaseRepository[Schedule]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Schedule)

    async def get_active(self) -> Sequence[Schedule]:
        result = await self.session.execute(
            select(Schedule).where(Schedule.is_active.is_(True))
        )
        return result.scalars().all()

    async def get_active_for_branch(self, branch_id: int) -> Sequence[Schedule]:
        """Bir subeye ait aktif anonslari getir (BRANCH + ALL)."""
        result = await self.session.execute(
            select(Schedule).where(
                Schedule.is_active.is_(True),
                (Schedule.target_type == TargetType.ALL)
                | (
                    (Schedule.target_type == TargetType.BRANCH)
                    & (Schedule.target_id == branch_id)
                ),
            )
        )
        return result.scalars().all()
