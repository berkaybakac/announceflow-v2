from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Uygulama konfigurasyonu. Tum degerler .env veya ortam degiskeniyle override edilebilir."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database (async — asyncpg)
    DATABASE_URL: str = "postgresql+asyncpg://admin:admin@localhost:5433/announceflow"

    # App
    APP_NAME: str = "AnnounceFlow"
    DEBUG: bool = False

    # JWT (Adim 2'de kullanilacak)
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60


settings = Settings()
