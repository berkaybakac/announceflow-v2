from datetime import date as date_, datetime, time as time_

from sqlalchemy import Date, DateTime, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class PrayerTime(Base):
    """Diyanet API 30 gunluk cache. Composite PK: date + city + district."""

    __tablename__ = "prayer_times"

    date: Mapped[date_] = mapped_column(Date, primary_key=True)
    city: Mapped[str] = mapped_column(String(100), primary_key=True)
    district: Mapped[str] = mapped_column(String(100), primary_key=True)
    fajr: Mapped[time_] = mapped_column(Time, nullable=False)
    sunrise: Mapped[time_] = mapped_column(Time, nullable=False)
    dhuhr: Mapped[time_] = mapped_column(Time, nullable=False)
    asr: Mapped[time_] = mapped_column(Time, nullable=False)
    maghrib: Mapped[time_] = mapped_column(Time, nullable=False)
    isha: Mapped[time_] = mapped_column(Time, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
