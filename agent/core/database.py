"""Agent SQLite Veritabani Katmani.

Blueprint 3D.4 standardi:
- 4 tablo: config, local_media, local_schedules, prayer_times
- PRAGMA journal_mode=WAL (SD kart koruması)
- PRAGMA busy_timeout=5000 (APScheduler ile cakisma onlemi)
- Alembic YASAK — idempotent IF NOT EXISTS

Singleton baglanti: Agent omru boyunca tek Connection nesnesi.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import aiosqlite

from agent.core.settings import agent_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema Version — OTA migration icin
# ---------------------------------------------------------------------------
CURRENT_SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# SQL — Idempotent tablo olusturma
# ---------------------------------------------------------------------------
_SQL_CREATE_CONFIG = """
CREATE TABLE IF NOT EXISTS config (
    key         TEXT PRIMARY KEY,
    value       TEXT
);
"""

_SQL_CREATE_LOCAL_MEDIA = """
CREATE TABLE IF NOT EXISTS local_media (
    id          INTEGER PRIMARY KEY,
    file_name   TEXT    NOT NULL,
    file_hash   TEXT    NOT NULL,
    type        TEXT    NOT NULL CHECK (type IN ('MUSIC', 'ANONS')),
    local_path  TEXT    NOT NULL
);
"""

_SQL_CREATE_LOCAL_SCHEDULES = """
CREATE TABLE IF NOT EXISTS local_schedules (
    id              INTEGER PRIMARY KEY,
    media_id        INTEGER NOT NULL,
    cron_expression TEXT,
    play_at         TEXT,
    end_time        TEXT,
    FOREIGN KEY (media_id) REFERENCES local_media(id)
);
"""

_SQL_CREATE_PRAYER_TIMES = """
CREATE TABLE IF NOT EXISTS prayer_times (
    date        TEXT PRIMARY KEY,
    fajr        TEXT NOT NULL,
    sunrise     TEXT NOT NULL,
    dhuhr       TEXT NOT NULL,
    asr         TEXT NOT NULL,
    maghrib     TEXT NOT NULL,
    isha        TEXT NOT NULL,
    fetched_at  TEXT NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Singleton Connection
# ---------------------------------------------------------------------------
_connection: Optional[aiosqlite.Connection] = None
_connection_lock = asyncio.Lock()


async def get_db() -> aiosqlite.Connection:
    """Singleton veritabani baglantisini dondurur.

    Ilk cagrildiginda baglanti olusturur, sonraki cagrilarda
    ayni nesneyi yeniden kullanir. Agent omru boyunca tek baglanti.
    """
    global _connection

    if _connection is not None:
        return _connection

    async with _connection_lock:
        if _connection is not None:
            return _connection

        db = await aiosqlite.connect(agent_settings.DB_PATH)
        db.row_factory = aiosqlite.Row

        try:
            # --- PRAGMA ayarlari (WAL + busy_timeout) ---
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute("PRAGMA foreign_keys=ON")
        except Exception:
            await db.close()
            raise

        _connection = db
        return db


async def close_db() -> None:
    """Veritabani baglantisini guvenli sekilde kapatir."""
    global _connection

    db: Optional[aiosqlite.Connection] = None
    async with _connection_lock:
        if _connection is not None:
            db = _connection
            _connection = None

    if db is not None:
        await db.close()
        logger.info("SQLite baglantisi kapatildi")


# ---------------------------------------------------------------------------
# init_db — Boot sequence'de cagirilir
# ---------------------------------------------------------------------------
async def init_db() -> None:
    """Veritabanini hazirlar: WAL + 4 tablo + varsayilan config.

    Idempotent: Kac kez calisirsa calissin ayni sonucu uretir.
    Boot sequence Adim 3'te cagirilir.
    """
    db = await get_db()

    # --- Tablolari olustur ---
    await db.execute(_SQL_CREATE_CONFIG)
    await db.execute(_SQL_CREATE_LOCAL_MEDIA)
    await db.execute(_SQL_CREATE_LOCAL_SCHEDULES)
    await db.execute(_SQL_CREATE_PRAYER_TIMES)

    # --- Varsayilan config degerleri (INSERT OR IGNORE — idempotent) ---
    default_values = [
        ("work_start", "08:00"),
        ("work_end", "20:00"),
        ("volume_music", "80"),
        ("volume_announce", "100"),
        ("prayer_margin", "1"),
        ("loop_active", "1"),
        ("kill_active", "0"),
        ("schema_version", str(CURRENT_SCHEMA_VERSION)),
    ]
    for key, value in default_values:
        await db.execute(
            "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
            (key, value),
        )

    await db.commit()

    # --- Dogrulama ---
    journal_mode = await db.execute_fetchall("PRAGMA journal_mode")
    schema_row = await db.execute_fetchall(
        "SELECT value FROM config WHERE key = 'schema_version'"
    )

    mode = journal_mode[0][0] if journal_mode else "unknown"
    version = schema_row[0][0] if schema_row else "unknown"

    logger.info(
        "init_db tamamlandi",
        extra={
            "journal_mode": mode,
            "schema_version": version,
            "db_path": agent_settings.DB_PATH,
        },
    )
