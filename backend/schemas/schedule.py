from datetime import datetime, timezone

from croniter import croniter
from pydantic import BaseModel, model_validator

from backend.models.media import TargetType


# ── Create / Update ─────────────────────────────────────────────


class ScheduleCreate(BaseModel):
    """Yeni schedule oluşturma şeması.

    XOR Kuralı: play_at veya cron_expression'dan tam olarak biri dolu olmalı.
    end_time kullanıcıdan ALINMAZ — Service katmanında hesaplanır.
    """

    media_id: int
    target_type: TargetType
    target_id: int | None = None
    target_group: str | None = None
    play_at: datetime | None = None
    cron_expression: str | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_xor_and_fields(self) -> "ScheduleCreate":
        has_play_at = self.play_at is not None
        has_cron = self.cron_expression is not None

        # XOR guard
        if has_play_at == has_cron:
            raise ValueError(
                "play_at ve cron_expression alanlarından tam olarak biri dolu olmalıdır (XOR)."
            )

        # cron_expression geçerlilik kontrolü
        if has_cron and self.cron_expression is not None and not croniter.is_valid(self.cron_expression):
            raise ValueError(
                f"Geçersiz cron ifadesi: '{self.cron_expression}'"
            )

        # play_at geçmiş tarih kontrolü
        if self.play_at is not None:
            now = datetime.now(tz=timezone.utc)
            play_at = self.play_at
            # Naive datetime'ı UTC kabul et
            if play_at.tzinfo is None:
                play_at = play_at.replace(tzinfo=timezone.utc)
            if play_at < now:
                raise ValueError("play_at geçmiş bir tarih olamaz.")

        return self


class ScheduleUpdate(BaseModel):
    """Schedule güncelleme şeması (partial update).

    Gönderilen alanlar üzerinden XOR kontrolü yapılır.
    """

    media_id: int | None = None
    target_type: TargetType | None = None
    target_id: int | None = None
    target_group: str | None = None
    play_at: datetime | None = None
    cron_expression: str | None = None
    is_active: bool | None = None

    # Sentinel: alanın gönderilip gönderilmediğini ayırt etmek için
    _play_at_set: bool = False
    _cron_set: bool = False

    @model_validator(mode="before")
    @classmethod
    def track_set_fields(cls, data: dict) -> dict:  # type: ignore[override]
        if isinstance(data, dict):
            data["_play_at_set"] = "play_at" in data
            data["_cron_set"] = "cron_expression" in data
        return data

    @model_validator(mode="after")
    def validate_xor_if_set(self) -> "ScheduleUpdate":
        # Her iki alan da açıkça gönderildiyse XOR kontrolü
        if self._play_at_set and self._cron_set:
            has_play_at = self.play_at is not None
            has_cron = self.cron_expression is not None
            if has_play_at == has_cron:
                raise ValueError(
                    "play_at ve cron_expression alanlarından tam olarak biri dolu olmalıdır (XOR)."
                )

        # cron_expression doğrulama
        if self._cron_set and self.cron_expression is not None:
            if not croniter.is_valid(self.cron_expression):
                raise ValueError(
                    f"Geçersiz cron ifadesi: '{self.cron_expression}'"
                )

        return self


# ── Read ─────────────────────────────────────────────────────────


class ScheduleRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    media_id: int
    media_file_name: str
    media_duration: int
    target_type: TargetType
    target_id: int | None
    target_group: str | None
    play_at: datetime | None
    cron_expression: str | None
    end_time: datetime | None
    is_active: bool
    created_at: datetime


# ── Conflict Check ───────────────────────────────────────────────


class ConflictCheckRequest(BaseModel):
    """Çakışma ön kontrol şeması (POST /check-conflict)."""

    media_id: int
    play_at: datetime
    target_type: TargetType
    target_id: int | None = None
    target_group: str | None = None
    exclude_schedule_id: int | None = None


class ConflictCheckResponse(BaseModel):
    has_conflict: bool
    conflicting_schedule: ScheduleRead | None = None


# ── Pagination ───────────────────────────────────────────────────


class PaginatedScheduleResponse(BaseModel):
    items: list[ScheduleRead]
    total: int
    page: int
    page_size: int
