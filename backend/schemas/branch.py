from datetime import time

from pydantic import BaseModel, Field


class BranchCreate(BaseModel):
    name: str
    city: str
    district: str
    group_tag: str | None = None


class BranchRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    city: str
    district: str
    group_tag: str | None
    token: str
    status: bool
    volume_music: int
    volume_announce: int


class BranchSettingsCreate(BaseModel):
    work_start: time
    work_end: time
    prayer_tracking: bool = False
    prayer_margin: int = Field(default=10, ge=0, le=30)
    city_code: int
    loop_mode: str = "shuffle_loop"


class BranchSettingsRead(BranchSettingsCreate):
    model_config = {"from_attributes": True}

    id: int
    branch_id: int


class BranchWithSettingsRead(BranchRead):
    settings: BranchSettingsRead | None = None
