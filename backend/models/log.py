from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, IdMixin

# Production'da JSONB (PostgreSQL index/sorgu desteği),
# test ortamında (SQLite) plain JSON'a düşer.
_JsonVariant = JSON().with_variant(JSONB, "postgresql")


class LogEntry(IdMixin, Base):
    """Şube cihazlarından merkeze akan yapılandırılmış log kaydı."""

    __tablename__ = "logs"

    branch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    context: Mapped[dict | None] = mapped_column(_JsonVariant, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

