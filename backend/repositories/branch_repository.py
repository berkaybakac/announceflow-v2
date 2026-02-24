from collections.abc import Sequence

from sqlalchemy import select, update
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

    async def get_by_token(self, token: str) -> Branch | None:
        result = await self.session.execute(
            select(Branch).where(Branch.token == token)
        )
        return result.scalar_one_or_none()

    # --- Heartbeat Monitor ---

    async def set_online_status(self, branch_id: int, is_online: bool) -> bool:
        """
        Branch online durumunu güncelle.

        Returns:
            True eğer satır güncellendiyse, False branch bulunamazsa.
        """
        result = await self.session.execute(
            update(Branch)
            .where(Branch.id == branch_id)
            .values(is_online=is_online)
        )
        return result.rowcount > 0

    async def set_bulk_offline(self, branch_ids: list[int]) -> int:
        """
        Birden fazla branch'i toplu offline yap.
        Reaper döngüsü tarafından çağrılır.

        Returns:
            Güncellenen satır sayısı.
        """
        if not branch_ids:
            return 0
        result = await self.session.execute(
            update(Branch)
            .where(Branch.id.in_(branch_ids))
            .where(Branch.is_online.is_(True))
            .values(is_online=False)
        )
        return result.rowcount

