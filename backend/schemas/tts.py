from datetime import datetime

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    language: str = Field(default="tr")
    voice_profile: str = Field(default="default")


class TTSJobRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    text_input: str
    voice_profile: str
    status: str
    media_id: int | None
    created_at: datetime
    processed_at: datetime | None
