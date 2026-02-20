from datetime import date, datetime, time

from pydantic import BaseModel


class PrayerTimeRead(BaseModel):
    model_config = {"from_attributes": True}

    date: date
    city: str
    district: str
    fajr: time
    sunrise: time
    dhuhr: time
    asr: time
    maghrib: time
    isha: time
    fetched_at: datetime
