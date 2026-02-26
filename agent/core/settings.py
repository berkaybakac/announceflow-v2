from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Agent cihaz konfigurasyonu. Tum degerler .env veya ortam degiskeniyle override edilebilir."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---
    DB_PATH: str = "agent.db"  # SQLite dosya yolu (WAL mode)

    # --- Boot ---
    TOKEN_PATH: str = "/boot/device_token.txt"  # Device token dosyasi

    # --- Logging ---
    LOG_LEVEL: str = "INFO"  # DEBUG | INFO | WARNING | ERROR

    # --- Scheduler ---
    SCHEDULER_ENABLED: bool = True  # APScheduler acik/kapali

    # --- Voice Engine ---
    VOICE_BACKEND: str = "libvlc"  # libvlc | tts
    DEFAULT_VOLUME: int = 80  # 0-100 (legacy default)

    # --- ALSA (Pi4 donanim ses kontrolu — legacy'den devralindi) ---
    ALSA_DEVICE: str = ""  # Ör: "plughw:2,0" — bossa auto-detect
    ALSA_CARD: str = ""  # Ör: "2" — bossa fallback zinciri
    ENABLE_HW_VOLUME: bool = True  # Pi4 amixer calibration aktif/pasif


agent_settings = AgentSettings()
