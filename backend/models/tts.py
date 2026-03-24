import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, IdMixin

if TYPE_CHECKING:
    from backend.models.media import MediaFile


class TTSJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


class TTSJob(IdMixin, Base):
    __tablename__ = "tts_jobs"

    text_input: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="tr")
    voice_profile: Mapped[str] = mapped_column(String(100), default="default")
    status: Mapped[TTSJobStatus] = mapped_column(
        Enum(TTSJobStatus), default=TTSJobStatus.PENDING, nullable=False
    )
    media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_files.id", ondelete="SET NULL"), nullable=True
    )
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    media: Mapped["MediaFile | None"] = relationship()
