from collections.abc import Sequence

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.media import MediaFile, MediaTarget, MediaType, TargetType
from backend.models.schedule import Schedule
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

    async def get_music_for_branch(
        self,
        branch_id: int,
        group_tag: str | None,
        limit: int | None = None,
    ) -> Sequence[MediaFile]:
        """
        Branch'e ait tüm MÜZİK dosyalarını 3'lü ACL kuralıyla getir.

        Çözümleme: ALL ∪ BRANCH(branch_id) ∪ GROUP(group_tag)
        DISTINCT ile aynı dosyanın birden fazla kuraldan eşleşmesi önlenir.
        """
        conditions = [
            MediaTarget.target_type == TargetType.ALL,
            (MediaTarget.target_type == TargetType.BRANCH)
            & (MediaTarget.target_id == branch_id),
        ]
        if group_tag:
            conditions.append(
                (MediaTarget.target_type == TargetType.GROUP)
                & (MediaTarget.target_group == group_tag)
            )

        stmt = (
            select(MediaFile)
            .join(MediaTarget, MediaTarget.media_id == MediaFile.id)
            .where(MediaFile.type == MediaType.MUSIC)
            .where(or_(*conditions))
            .distinct()
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def is_accessible_for_branch(
        self,
        media_id: int,
        branch_id: int,
        group_tag: str | None,
    ) -> bool:
        """Device branch'in media dosyasına erişim yetkisini doğrula.

        MUSIC:
        - media_targets: ALL ∪ BRANCH(branch_id) ∪ GROUP(group_tag)

        ANONS:
        - aktif schedule hedefleri: ALL ∪ BRANCH(branch_id) ∪ GROUP(group_tag)
        """
        music_acl_conditions = [
            MediaTarget.target_type == TargetType.ALL,
            and_(
                MediaTarget.target_type == TargetType.BRANCH,
                MediaTarget.target_id == branch_id,
            ),
        ]
        schedule_acl_conditions = [
            Schedule.target_type == TargetType.ALL,
            and_(
                Schedule.target_type == TargetType.BRANCH,
                Schedule.target_id == branch_id,
            ),
        ]
        if group_tag:
            music_acl_conditions.append(
                and_(
                    MediaTarget.target_type == TargetType.GROUP,
                    MediaTarget.target_group == group_tag,
                )
            )
            schedule_acl_conditions.append(
                and_(
                    Schedule.target_type == TargetType.GROUP,
                    Schedule.target_group == group_tag,
                )
            )

        music_acl_exists = exists(
            select(MediaTarget.id).where(
                MediaTarget.media_id == MediaFile.id,
                or_(*music_acl_conditions),
            )
        )
        anons_acl_exists = exists(
            select(Schedule.id).where(
                Schedule.media_id == MediaFile.id,
                Schedule.is_active.is_(True),
                or_(*schedule_acl_conditions),
            )
        )

        stmt = select(MediaFile.id).where(
            MediaFile.id == media_id,
            or_(
                and_(MediaFile.type == MediaType.MUSIC, music_acl_exists),
                and_(MediaFile.type == MediaType.ANONS, anons_acl_exists),
            ),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None


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
