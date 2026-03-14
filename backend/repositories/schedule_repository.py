from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, func, or_, select, true
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.media import MediaFile, MediaType, TargetType
from backend.models.schedule import Schedule
from backend.repositories.base import BaseRepository


class ScheduleRepository(BaseRepository[Schedule]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Schedule)

    # ── Mevcut metotlar (Manifest API tarafından kullanılıyor) ──

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
    ) -> Sequence[Row[tuple[Schedule, MediaFile]]]:
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

    # ── Yeni metotlar (Scheduler CRUD API) ──────────────────────

    async def get_by_id_with_media(
        self, schedule_id: int
    ) -> Row[tuple[Schedule, MediaFile]] | None:
        """Schedule + media JOIN ile tek kayıt döndürür."""
        stmt = (
            select(Schedule, MediaFile)
            .join(MediaFile, MediaFile.id == Schedule.media_id)
            .where(Schedule.id == schedule_id)
        )
        result = await self.session.execute(stmt)
        return result.first()

    async def get_all_paginated(
        self,
        page: int,
        page_size: int,
        is_active: bool | None = None,
    ) -> tuple[Sequence[Row[tuple[Schedule, MediaFile]]], int]:
        """Dashboard için paginated schedule listesi (media JOIN).

        Returns: (rows, total_count)
        """
        # Base conditions
        conditions = []
        if is_active is not None:
            conditions.append(Schedule.is_active.is_(is_active))

        # Count query
        count_stmt = select(func.count(Schedule.id))
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Data query
        stmt = (
            select(Schedule, MediaFile)
            .join(MediaFile, MediaFile.id == Schedule.media_id)
            .order_by(Schedule.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if conditions:
            stmt = stmt.where(*conditions)

        result = await self.session.execute(stmt)
        return result.all(), total

    async def find_overlapping_one_time(
        self,
        play_at: datetime,
        end_time: datetime,
        target_type: TargetType | str,
        target_id: int | None,
        target_group: str | None,
        exclude_id: int | None = None,
    ) -> Row[tuple[Schedule, MediaFile]] | None:
        """Zaman aralığı + hedef kesişimi çakışma sorgusu.

        Strict interval overlap: A.play_at < B.end_time AND B.play_at < A.end_time

        Hedef kuralları:
        - ALL vs herhangi = çakışır
        - Aynı tip + aynı değer = çakışır
        - Farklı BRANCH'ler veya farklı GROUP'lar = çakışmaz
        """
        # Zaman çakışma koşulu
        time_overlap = and_(
            Schedule.play_at < end_time,
            Schedule.end_time > play_at,
        )

        # Hedef çakışma koşulları
        target_conditions = [
            # Mevcut kayıt ALL ise her şeyle çakışır
            Schedule.target_type == TargetType.ALL,
        ]

        # Kandidat ALL ise mevcut her kayıtla çakışır (zaten yukarıda var,
        # ama ayrıca candidate tarafı olarak da ALL'u ekleyelim)
        if target_type == TargetType.ALL or target_type == "ALL":
            # ALL candidate — tüm aktif tek seferlik schedule'larla çakışır
            pass  # target_conditions zaten ALL'u kapsıyor, ek koşul gerekmiyor
        else:
            # Aynı tip + aynı değer çakışması
            if target_type == TargetType.BRANCH or target_type == "BRANCH":
                target_conditions.append(
                    and_(
                        Schedule.target_type == TargetType.BRANCH,
                        Schedule.target_id == target_id,
                    )
                )
            elif target_type == TargetType.GROUP or target_type == "GROUP":
                target_conditions.append(
                    and_(
                        Schedule.target_type == TargetType.GROUP,
                        Schedule.target_group == target_group,
                    )
                )

        # Candidate ALL ise — tüm hedeflerle çakışır
        if target_type == TargetType.ALL or target_type == "ALL":
            target_filter = true()  # Hedef filtresi yok — tümüyle çakışır
        else:
            target_filter = or_(*target_conditions)

        stmt = (
            select(Schedule, MediaFile)
            .join(MediaFile, MediaFile.id == Schedule.media_id)
            .where(
                Schedule.is_active.is_(True),
                Schedule.play_at.is_not(None),
                time_overlap,
                target_filter,
            )
        )

        if exclude_id is not None:
            stmt = stmt.where(Schedule.id != exclude_id)

        stmt = stmt.limit(1)

        result = await self.session.execute(stmt)
        return result.first()
