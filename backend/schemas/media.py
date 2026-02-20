from datetime import datetime

from pydantic import BaseModel

from backend.models.media import MediaType, TargetType


class MediaFileRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    file_name: str
    file_path: str
    file_hash: str
    type: MediaType
    duration: int
    created_at: datetime


class MediaTargetCreate(BaseModel):
    target_type: TargetType
    target_id: int | None = None
    target_group: str | None = None


class MediaTargetRead(MediaTargetCreate):
    model_config = {"from_attributes": True}

    id: int
    media_id: int


class MediaFileWithTargetsRead(MediaFileRead):
    targets: list[MediaTargetRead] = []
