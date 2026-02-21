from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Uygulama konfigurasyonu. Tum degerler .env veya ortam degiskeniyle override edilebilir."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database (async — asyncpg)
    DATABASE_URL: str = Field(...)

    # App
    APP_NAME: str = "AnnounceFlow"
    DEBUG: bool = False

    # JWT
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 saat (dashboard)
    DEVICE_TOKEN_EXPIRE_DAYS: int = 30  # Agent

    # Media Storage (lokal dev icin goreceli, Docker'da .env ile /data/media override)
    MEDIA_STORAGE_PATH: str = "./data/media"
    MEDIA_TEMP_PATH: str = "./data/media/temp"
    MAX_UPLOAD_SIZE_MB: int = 500

    # TTS (Coqui XTTS v2)
    TTS_MODEL_NAME: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    TTS_MAX_TEXT_LENGTH: int = 1000


settings = Settings()
