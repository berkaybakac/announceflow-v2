from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, IdMixin
from backend.models.media import TargetType


class Schedule(IdMixin, Base):
    __tablename__ = "schedules"

    media_id: Mapped[int] = mapped_column(
        ForeignKey("media_files.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[TargetType] = mapped_column(
        Enum(TargetType), nullable=False
    )
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    play_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cron_expression: Mapped[str | None] = mapped_column(String(100), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )