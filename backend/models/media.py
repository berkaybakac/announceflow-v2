import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, IdMixin


class MediaType(str, enum.Enum):
    MUSIC = "MUSIC"
    ANONS = "ANONS"


class TargetType(str, enum.Enum):
    BRANCH = "BRANCH"
    GROUP = "GROUP"
    ALL = "ALL"


class MediaFile(IdMixin, Base):
    __tablename__ = "media_files"

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[MediaType] = mapped_column(Enum(MediaType), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    targets: Mapped[list["MediaTarget"]] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )


class MediaTarget(IdMixin, Base):
    __tablename__ = "media_targets"

    media_id: Mapped[int] = mapped_column(
        ForeignKey("media_files.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[TargetType] = mapped_column(
        Enum(TargetType), nullable=False
    )
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_group: Mapped[str | None] = mapped_column(String(100), nullable=True)

    media: Mapped["MediaFile"] = relationship(back_populates="targets")
