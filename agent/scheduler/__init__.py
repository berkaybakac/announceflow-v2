"""APScheduler Iskeleti — BackgroundScheduler + SQLAlchemyJobStore.

Blueprint Kurali:
- Job persistence: SQLAlchemyJobStore -> agent.db (ayni dosya)
- NullPool: Baglanti havuzu KAPALI — her islemde ac-kapat (RAM tasarrufu)
- Bu adimda sadece scheduler nesnesi baslatilir, HICBIR job register edilmez.
- Job ekleme Faz 3 Adim 3'te (Priority Manager) yapilacak.

APScheduler <-> aiosqlite izolasyonu:
- APScheduler senkron SQLAlchemy kullanir (kendi internal thread'i var).
- Agent tablolari aiosqlite ile erisir.
- WAL mode + busy_timeout=5000 ile cakisma riski pratikle sifir.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool

from agent.core.settings import agent_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton Scheduler
# ---------------------------------------------------------------------------
_scheduler: Optional[BackgroundScheduler] = None


def _create_engine_with_wal() -> object:
    """WAL mode ve busy_timeout ile SQLAlchemy engine olusturur.

    NullPool: Her islemde baglanti ac-kapat.
    Pi4 (1GB RAM) icin idle connection overhead'i sifir.
    """
    db_url = f"sqlite:///{agent_settings.DB_PATH}"

    engine = create_engine(
        db_url,
        poolclass=NullPool,
        connect_args={"timeout": 5},  # busy_timeout (saniye)
    )

    # --- WAL mode'u engine seviyesinde zorunlu kil ---
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn: object, _: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[union-attr]
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def get_scheduler() -> BackgroundScheduler:
    """Singleton scheduler nesnesini dondurur.

    Ilk cagrildiginda BackgroundScheduler + SQLAlchemyJobStore olusturur.
    Sonraki cagrilarda ayni nesneyi yeniden kullanir.
    """
    global _scheduler

    if _scheduler is not None:
        return _scheduler

    engine = _create_engine_with_wal()

    jobstore = SQLAlchemyJobStore(engine=engine)

    scheduler = BackgroundScheduler(
        jobstores={"default": jobstore},
        job_defaults={
            "coalesce": True,       # Kacirilmis calismalari birlestir
            "max_instances": 1,     # Ayni job ayni anda 1 kez calisir
            "misfire_grace_time": 60,  # 60 sn icerisinde hala calistir
        },
    )

    _scheduler = scheduler
    return scheduler


async def start_scheduler() -> None:
    """Scheduler'i baslatir. Boot sequence'de cagirilir.

    Bu adimda hicbir job register edilmez.
    Job ekleme Faz 3 Adim 3'te yapilacak.
    """
    if not agent_settings.SCHEDULER_ENABLED:
        logger.info("APScheduler devre disi (SCHEDULER_ENABLED=False)")
        return

    scheduler = get_scheduler()

    if scheduler.running:
        logger.warning("Scheduler zaten calisiyor, tekrar baslatilmadi")
        return

    await asyncio.to_thread(scheduler.start, False)
    logger.info(
        "APScheduler baslatildi",
        extra={
            "jobstore": "SQLAlchemyJobStore",
            "db_path": agent_settings.DB_PATH,
        },
    )


async def shutdown_scheduler() -> None:
    """Scheduler'i guvenli sekilde kapatir."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        await asyncio.to_thread(_scheduler.shutdown, False)
        logger.info("APScheduler kapatildi")

    _scheduler = None
