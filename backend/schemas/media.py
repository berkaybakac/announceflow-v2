from datetime import datetime

from pydantic import BaseModel, Field

from backend.models.media import MediaType, TargetType


class MediaFileCreate(BaseModel):
    file_name: str
    file_path: str
    file_hash: str
    type: MediaType
    duration: int = 0
    size_bytes: int = 0


class MediaFileRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    file_name: str
    file_path: str
    file_hash: str
    type: MediaType
    duration: int
    size_bytes: int
    created_at: datetime


class MediaUploadResponse(BaseModel):
    media_id: int
    file_name: str
    status: str
    message: str


class MediaTargetCreate(BaseModel):
    target_type: TargetType
    target_id: int | None = None
    target_group: str | None = None


class MediaTargetRead(MediaTargetCreate):
    model_config = {"from_attributes": True}

    id: int
    media_id: int


class MediaFileWithTargetsRead(MediaFileRead):
    targets: list[MediaTargetRead] = Field(default_factory=list)
