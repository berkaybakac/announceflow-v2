import datetime
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.prayer_time import PrayerTime
from backend.repositories.base import BaseRepository


class PrayerTimeRepository(BaseRepository[PrayerTime]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PrayerTime)

    async def get_by_date_location(
        self, date: datetime.date, city: str, district: str
    ) -> PrayerTime | None:
        """Composite PK ile tek kayit getir."""
        return await self.session.get(PrayerTime, (date, city, district))

    async def get_range(
        self,
        city: str,
        district: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> Sequence[PrayerTime]:
        """Tarih araligi icin namaz vakitlerini getir."""
        result = await self.session.execute(
            select(PrayerTime).where(
                PrayerTime.city == city,
                PrayerTime.district == district,
                PrayerTime.date >= start_date,
                PrayerTime.date <= end_date,
            )
        )
        return result.scalars().all()
