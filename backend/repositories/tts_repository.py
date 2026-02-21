from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.tts import TTSJob
from backend.repositories.base import BaseRepository


class TTSJobRepository(BaseRepository[TTSJob]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TTSJob)
