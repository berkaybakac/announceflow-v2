from datetime import datetime

from pydantic import BaseModel

from backend.models.media import TargetType


class ScheduleCreate(BaseModel):
    media_id: int
    target_type: TargetType
    target_id: int | None = None
    target_group: str | None = None
    play_at: datetime | None = None
    cron_expression: str | None = None
    end_time: datetime | None = None
    is_active: bool = True


class ScheduleRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    media_id: int
    target_type: TargetType
    target_id: int | None
    target_group: str | None
    play_at: datetime | None
    cron_expression: str | None
    end_time: datetime | None
    is_active: bool

# TODO: Agent (Raspberry Pi) sync endpoint'i yazılırken (Adım 3), cihazın payload ihtiyacına göre ScheduleWithMediaRead şeması buraya eklenecek.
