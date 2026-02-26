from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, IdMixin


class Branch(IdMixin, Base):
    __tablename__ = "branches"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    group_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    token: Mapped[str] = mapped_column(
        String(500),
        unique=True,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    volume_music: Mapped[int] = mapped_column(Integer, default=50)
    volume_announce: Mapped[int] = mapped_column(Integer, default=80)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sync_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # 1-to-1 relationship
    settings: Mapped["BranchSettings"] = relationship(
        back_populates="branch",
        uselist=False,
        cascade="all, delete-orphan",
    )


class BranchSettings(IdMixin, Base):
    __tablename__ = "branch_settings"

    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    work_start: Mapped[time] = mapped_column(Time, nullable=False)
    work_end: Mapped[time] = mapped_column(Time, nullable=False)
    prayer_tracking: Mapped[bool] = mapped_column(Boolean, default=False)
    prayer_margin: Mapped[int] = mapped_column(Integer, default=10)
    city_code: Mapped[int] = mapped_column(Integer, nullable=False)
    loop_mode: Mapped[str] = mapped_column(String(20), default="shuffle_loop")

    branch: Mapped["Branch"] = relationship(back_populates="settings")
