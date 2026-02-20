from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.media import MediaFile, MediaTarget, MediaType, TargetType
from backend.repositories.base import BaseRepository


class MediaRepository(BaseRepository[MediaFile]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MediaFile)

    async def get_by_type(self, media_type: MediaType) -> Sequence[MediaFile]:
        result = await self.session.execute(
            select(MediaFile).where(MediaFile.type == media_type)
        )
        return result.scalars().all()

    async def get_by_hash(self, file_hash: str) -> MediaFile | None:
        result = await self.session.execute(
            select(MediaFile).where(MediaFile.file_hash == file_hash)
        )
        return result.scalar_one_or_none()


class MediaTargetRepository(BaseRepository[MediaTarget]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MediaTarget)

    async def get_targets_for_branch(self, branch_id: int) -> Sequence[MediaTarget]:
        """Bir subeye atanmis muzikleri getir (BRANCH + ALL)."""
        result = await self.session.execute(
            select(MediaTarget).where(
                (MediaTarget.target_type == TargetType.ALL)
                | (
                    (MediaTarget.target_type == TargetType.BRANCH)
                    & (MediaTarget.target_id == branch_id)
                )
            )
        )
        return result.scalars().all()

    async def get_targets_for_group(self, group_tag: str) -> Sequence[MediaTarget]:
        """Bir gruba atanmis muzikleri getir (GROUP + ALL)."""
        result = await self.session.execute(
            select(MediaTarget).where(
                (MediaTarget.target_type == TargetType.ALL)
                | (
                    (MediaTarget.target_type == TargetType.GROUP)
                    & (MediaTarget.target_group == group_tag)
                )
            )
        )
        return result.scalars().all()
