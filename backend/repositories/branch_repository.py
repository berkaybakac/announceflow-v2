from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.branch import Branch, BranchSettings
from backend.repositories.base import BaseRepository


class BranchRepository(BaseRepository[Branch]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Branch)

    async def get_with_settings(self, branch_id: int) -> Branch | None:
        result = await self.session.execute(
            select(Branch)
            .options(selectinload(Branch.settings))
            .where(Branch.id == branch_id)
        )
        return result.scalar_one_or_none()

    async def get_by_city(self, city: str) -> Sequence[Branch]:
        result = await self.session.execute(
            select(Branch).where(Branch.city == city)
        )
        return result.scalars().all()

    async def get_by_group(self, group_tag: str) -> Sequence[Branch]:
        result = await self.session.execute(
            select(Branch).where(Branch.group_tag == group_tag)
        )
        return result.scalars().all()
