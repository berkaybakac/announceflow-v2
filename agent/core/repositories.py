"""Agent Repository Katmani — Repository Pattern.

Her tablo icin ayri Repository sinifi.
Is mantigi (service layer) dogrudan SQL yazmaz,
Repository arayuzunu kullanir.

Blueprint Kural: Veri erisimi ile is mantigi birbirinden ayrilir.
"""

from __future__ import annotations

import logging
from typing import Any, Optional


from agent.core.database import get_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ConfigRepository — Key-Value Store
# ---------------------------------------------------------------------------
class ConfigRepository:
    """config tablosu icin veri erisim katmani.

    Tek satirlik key-value store: work_start, work_end,
    volume_music, volume_announce, prayer_margin,
    loop_active, kill_active, schema_version.
    """

    async def get(self, key: str) -> Optional[str]:
        """Tek bir config degerini dondurur. Yoksa None."""
        db = await get_db()
        cursor = await db.execute(
            "SELECT value FROM config WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def set(self, key: str, value: str) -> None:
        """Config degerini gunceller veya olusturur (upsert)."""
        db = await get_db()
        await db.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await db.commit()
        logger.debug("Config guncellendi", extra={"key": key, "value": value})

    async def get_all(self) -> dict[str, str]:
        """Tum config degerlerini dict olarak dondurur."""
        db = await get_db()
        cursor = await db.execute("SELECT key, value FROM config")
        rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}

    async def set_many(self, items: dict[str, str]) -> None:
        """Birden fazla config degerini toplu gunceller."""
        db = await get_db()
        for key, value in items.items():
            await db.execute(
                "INSERT INTO config (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        await db.commit()
        logger.debug(
            "Config toplu guncellendi", extra={"keys": list(items.keys())}
        )


# ---------------------------------------------------------------------------
# LocalMediaRepository
# ---------------------------------------------------------------------------
class LocalMediaRepository:
    """local_media tablosu icin veri erisim katmani.

    Manifest sync sonrasi dosya kayitlarini yonetir.
    """

    async def get_by_id(self, media_id: int) -> Optional[dict[str, Any]]:
        """ID ile medya kaydini dondurur."""
        db = await get_db()
        cursor = await db.execute(
            "SELECT id, file_name, file_hash, type, local_path "
            "FROM local_media WHERE id = ?",
            (media_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_all(self) -> list[dict[str, Any]]:
        """Tum lokal medya kayitlarini dondurur."""
        db = await get_db()
        cursor = await db.execute(
            "SELECT id, file_name, file_hash, type, local_path "
            "FROM local_media"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_by_type(self, media_type: str) -> list[dict[str, Any]]:
        """Tipe gore (MUSIC/ANONS) medya kayitlarini dondurur."""
        db = await get_db()
        cursor = await db.execute(
            "SELECT id, file_name, file_hash, type, local_path "
            "FROM local_media WHERE type = ?",
            (media_type,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def upsert(
        self,
        media_id: int,
        file_name: str,
        file_hash: str,
        media_type: str,
        local_path: str,
    ) -> None:
        """Medya kaydini ekler veya gunceller (sync sonrasi)."""
        db = await get_db()
        await db.execute(
            "INSERT INTO local_media (id, file_name, file_hash, type, local_path) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "file_name = excluded.file_name, "
            "file_hash = excluded.file_hash, "
            "type = excluded.type, "
            "local_path = excluded.local_path",
            (media_id, file_name, file_hash, media_type, local_path),
        )
        await db.commit()

    async def delete(self, media_id: int) -> None:
        """Medya kaydini siler (manifest diff sonrasi temizlik)."""
        db = await get_db()
        await db.execute("DELETE FROM local_media WHERE id = ?", (media_id,))
        await db.commit()

    async def get_by_hash(self, file_hash: str) -> Optional[dict[str, Any]]:
        """Hash ile medya kaydini dondurur (sync dogrulama icin)."""
        db = await get_db()
        cursor = await db.execute(
            "SELECT id, file_name, file_hash, type, local_path "
            "FROM local_media WHERE file_hash = ?",
            (file_hash,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# LocalScheduleRepository
# ---------------------------------------------------------------------------
class LocalScheduleRepository:
    """local_schedules tablosu icin veri erisim katmani.

    APScheduler job'lari icin kaynak veri. Sync ile guncellenir.
    """

    async def get_by_id(
        self, schedule_id: int
    ) -> Optional[dict[str, Any]]:
        """ID ile schedule kaydini dondurur."""
        db = await get_db()
        cursor = await db.execute(
            "SELECT id, media_id, cron_expression, play_at, end_time "
            "FROM local_schedules WHERE id = ?",
            (schedule_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_all(self) -> list[dict[str, Any]]:
        """Tum schedule kayitlarini dondurur."""
        db = await get_db()
        cursor = await db.execute(
            "SELECT id, media_id, cron_expression, play_at, end_time "
            "FROM local_schedules"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def upsert(
        self,
        schedule_id: int,
        media_id: int,
        cron_expression: Optional[str],
        play_at: Optional[str],
        end_time: Optional[str],
    ) -> None:
        """Schedule kaydini ekler veya gunceller."""
        db = await get_db()
        await db.execute(
            "INSERT INTO local_schedules (id, media_id, cron_expression, play_at, end_time) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "media_id = excluded.media_id, "
            "cron_expression = excluded.cron_expression, "
            "play_at = excluded.play_at, "
            "end_time = excluded.end_time",
            (schedule_id, media_id, cron_expression, play_at, end_time),
        )
        await db.commit()

    async def delete(self, schedule_id: int) -> None:
        """Schedule kaydini siler."""
        db = await get_db()
        await db.execute(
            "DELETE FROM local_schedules WHERE id = ?", (schedule_id,)
        )
        await db.commit()

    async def delete_all(self) -> None:
        """Tum schedule kayitlarini siler (full sync sonrasi)."""
        db = await get_db()
        await db.execute("DELETE FROM local_schedules")
        await db.commit()


# ---------------------------------------------------------------------------
# PrayerTimeRepository
# ---------------------------------------------------------------------------
class PrayerTimeRepository:
    """prayer_times tablosu icin veri erisim katmani.

    Diyanet API'den 30 gunluk cache. Tarih bazli sorgulama.
    """

    async def get_by_date(self, date: str) -> Optional[dict[str, Any]]:
        """Belirli bir tarihin ezan vakitlerini dondurur.

        Args:
            date: ISO format tarih (YYYY-MM-DD).
        """
        db = await get_db()
        cursor = await db.execute(
            "SELECT date, fajr, sunrise, dhuhr, asr, maghrib, isha, fetched_at "
            "FROM prayer_times WHERE date = ?",
            (date,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_cached_range(self) -> dict[str, Any]:
        """Cache'deki en eski ve en yeni tarihi dondurur.

        Returns:
            {"min_date": str | None, "max_date": str | None, "count": int}
        """
        db = await get_db()
        cursor = await db.execute(
            "SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(*) as count "
            "FROM prayer_times"
        )
        row = await cursor.fetchone()
        return dict(row) if row else {"min_date": None, "max_date": None, "count": 0}

    async def bulk_upsert(self, records: list[dict[str, str]]) -> None:
        """30 gunluk ezan verisi toplu ekler/gunceller.

        Args:
            records: [{"date": "...", "fajr": "...", ..., "fetched_at": "..."}]
        """
        db = await get_db()
        for rec in records:
            await db.execute(
                "INSERT INTO prayer_times (date, fajr, sunrise, dhuhr, asr, maghrib, isha, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(date) DO UPDATE SET "
                "fajr = excluded.fajr, sunrise = excluded.sunrise, "
                "dhuhr = excluded.dhuhr, asr = excluded.asr, "
                "maghrib = excluded.maghrib, isha = excluded.isha, "
                "fetched_at = excluded.fetched_at",
                (
                    rec["date"],
                    rec["fajr"],
                    rec["sunrise"],
                    rec["dhuhr"],
                    rec["asr"],
                    rec["maghrib"],
                    rec["isha"],
                    rec["fetched_at"],
                ),
            )
        await db.commit()
        logger.info(
            "Ezan verileri guncellendi", extra={"record_count": len(records)}
        )

    async def delete_before(self, date: str) -> int:
        """Belirli bir tarihten onceki kayitlari siler (temizlik).

        Returns:
            Silinen kayit sayisi.
        """
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM prayer_times WHERE date < ?", (date,)
        )
        await db.commit()
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(
                "Eski ezan verisi temizlendi",
                extra={"before": date, "deleted": deleted},
            )
        return deleted
