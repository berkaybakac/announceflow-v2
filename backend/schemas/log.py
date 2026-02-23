from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LogLevel(str, Enum):
    """İzin verilen log seviyeleri."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogEntryCreate(BaseModel):
    """Agent'ın gönderdiği tek bir log kaydı."""

    level: LogLevel = LogLevel.INFO
    message: str = Field(..., max_length=2000)
    context: dict[str, Any] | None = None
    created_at: datetime


class LogBatchCreate(BaseModel):
    """Agent'ın toplu gönderdiği log paketi. Maksimum 100 kayıt."""

    logs: list[LogEntryCreate] = Field(..., max_length=100)


class LogEntryRead(BaseModel):
    """Veritabanından okunan log kaydı."""

    id: int
    branch_id: int
    level: LogLevel
    message: str
    context: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}
