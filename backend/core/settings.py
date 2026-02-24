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
    MANIFEST_MAX_FILES: int = Field(200, ge=1)

    # MQTT (Heartbeat Monitor)
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_TOPIC_STATUS: str = "announceflow/+/+/status"
    MQTT_TOPIC_LWT: str = "announceflow/+/+/lwt"
    MQTT_HEARTBEAT_TIMEOUT_SECONDS: int = 180  # 3 dakika
    MQTT_REAPER_INTERVAL_SECONDS: int = 60  # 1 dakikada bir kontrol
    MQTT_TELEMETRY_CACHE_MAX_BRANCHES: int = 5000
    MQTT_TELEMETRY_OFFLINE_TTL_SECONDS: int = 86400
    MQTT_TELEMETRY_MAX_STRING_LENGTH: int = 512

    # TTS (Coqui XTTS v2)
    COQUI_TOS_AGREED: bool = False
    TTS_MODEL_NAME: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    TTS_MAX_TEXT_LENGTH: int = 1000
    TTS_VOICE_PROFILE_REGISTRY_PATH: str = "./backend/config/voice_profiles.json"


settings = Settings()
