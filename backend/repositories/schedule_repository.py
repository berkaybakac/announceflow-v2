from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.media import MediaFile, MediaType, TargetType
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

    async def get_schedules_for_branch_with_media(
        self,
        branch_id: int,
        group_tag: str | None,
        limit: int | None = None,
    ) -> Sequence[tuple[Schedule, MediaFile]]:
        """
        Branch'e ait aktif anons schedule'larını media bilgisiyle getir.

        Çözümleme: ALL ∪ BRANCH(branch_id) ∪ GROUP(group_tag)
        Tek sorguda Schedule + MediaFile JOIN yaparak N+1 önlenir.
        """
        conditions = [
            Schedule.target_type == TargetType.ALL,
            (Schedule.target_type == TargetType.BRANCH)
            & (Schedule.target_id == branch_id),
        ]
        if group_tag:
            conditions.append(
                (Schedule.target_type == TargetType.GROUP)
                & (Schedule.target_group == group_tag)
            )

        stmt = (
            select(Schedule, MediaFile)
            .join(MediaFile, MediaFile.id == Schedule.media_id)
            .where(Schedule.is_active.is_(True))
            .where(MediaFile.type == MediaType.ANONS)
            .where(or_(*conditions))
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return result.all()
