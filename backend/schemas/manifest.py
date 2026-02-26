from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ManifestMediaItem(BaseModel):
    """Tek bir medya dosyası bilgisi — Agent'ın diff yapması için yeterli."""

    id: int
    file_name: str
    file_hash: str
    type: str
    size_bytes: int
    download_url: str


class ManifestScheduleItem(BaseModel):
    """Anons zamanlama bilgisi + ilişkili medya detayları."""

    id: int
    media_id: int
    media_file_name: str
    media_file_hash: str
    media_size_bytes: int
    media_download_url: str
    play_at: datetime | None = None
    cron_expression: str | None = None
    end_time: datetime | None = None


class ManifestSettingsItem(BaseModel):
    """Branch ayarları — Agent'ın ihtiyaç duyduğu subset."""

    work_start: str  # "HH:MM" — strftime("%H:%M") ile üretilir
    work_end: str  # "HH:MM"
    volume_music: int
    volume_announce: int
    loop_mode: str


class ManifestResponse(BaseModel):
    """Agent'a dönen tam manifest JSON."""

    branch_id: int
    generated_at: str  # ISO 8601
    music: list[ManifestMediaItem]
    announcements: list[ManifestScheduleItem]
    settings: ManifestSettingsItem | None = None


class SyncConfirmRequest(BaseModel):
    """Agent sync bitirdiğinde gönderir."""

    synced_files_count: int
    status: Literal["ok", "partial"] = "ok"


class SyncConfirmResponse(BaseModel):
    """Sync onay cevabı."""

    ok: bool
    message: str
