"""
In-Memory Telemetri Cache — Singleton.

Şubelerden (Agent) gelen periyodik telemetri verilerini RAM'de tutar.
Veritabanına KESİNLİKLE yazılmaz (Blueprint kuralı 3B.1).
Dashboard GET endpoint'i bu cache'den okur.

Neden dict yeterli?
- asyncio tek thread'de çalışır → race condition riski yok
- Sunucu restart olursa cache sıfırlanır → agent 60 sn içinde tekrar gönderir
- Redis/Celery YASAKTIR (Blueprint)
"""

import time
from typing import Any


class TelemetryCache:
    """
    Thread-safe olmayan ama asyncio-safe in-memory cache.

    Yapı:
    {
        branch_id: {
            "status": True,
            "current_track": "song.mp3",
            "disk_usage": 45.2,
            "cpu_temp": 52.1,
            "ram_usage": 38.5,
            "last_sync": "2026-02-24T09:00:00Z",
            "loop_active": True,
            "last_seen": 1740380000.0  # monotonic timestamp
        }
    }
    """

    # Blueprint'te tanımlı payload alanları
    ALLOWED_FIELDS: frozenset[str] = frozenset(
        {
            "status",
            "current_track",
            "disk_usage",
            "cpu_temp",
            "ram_usage",
            "last_sync",
            "loop_active",
        }
    )
    _NUMERIC_RANGES: dict[str, tuple[float, float]] = {
        "disk_usage": (0.0, 100.0),
        "ram_usage": (0.0, 100.0),
        "cpu_temp": (-40.0, 150.0),
    }
    _STRING_FIELDS: frozenset[str] = frozenset({"current_track", "last_sync"})
    _BOOLEAN_FIELDS: frozenset[str] = frozenset({"status", "loop_active"})

    def __init__(self) -> None:
        self._store: dict[int, dict[str, Any]] = {}

    @staticmethod
    def _is_valid_number(value: Any, minimum: float, maximum: float) -> bool:
        """bool dışındaki sayısal değerleri ve aralıklarını doğrula."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        value_float = float(value)
        return minimum <= value_float <= maximum

    def _sanitize_payload(
        self,
        payload: dict[str, Any],
        *,
        max_string_length: int,
    ) -> dict[str, Any]:
        """Sadece güvenli alanları tip/boyut kontrolü ile döndür."""
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            if key not in self.ALLOWED_FIELDS:
                continue

            if key in self._BOOLEAN_FIELDS:
                if isinstance(value, bool):
                    sanitized[key] = value
                continue

            if key in self._STRING_FIELDS:
                if isinstance(value, str) and len(value) <= max_string_length:
                    sanitized[key] = value
                continue

            value_range = self._NUMERIC_RANGES.get(key)
            if value_range is None:
                continue
            minimum, maximum = value_range
            if self._is_valid_number(value, minimum, maximum):
                sanitized[key] = float(value)

        return sanitized

    def update(
        self,
        branch_id: int,
        payload: dict[str, Any],
        *,
        max_string_length: int = 512,
        force_status: bool | None = None,
    ) -> None:
        """
        Telemetri verisini merge ederek güncelle.

        Bilinmeyen veya geçersiz alanlar filtrelenir; last_seen her durumda yenilenir.
        """
        sanitized = self._sanitize_payload(
            payload,
            max_string_length=max_string_length,
        )
        if force_status is not None:
            sanitized["status"] = force_status

        entry = dict(self._store.get(branch_id, {}))
        entry.update(sanitized)
        entry["last_seen"] = time.monotonic()
        self._store[branch_id] = entry

    def mark_offline(self, branch_id: int, *, create_if_missing: bool = False) -> bool:
        """Branch'i cache'de offline olarak işaretle."""
        entry = self._store.get(branch_id)
        if entry is None and not create_if_missing:
            return False

        data = dict(entry or {})
        data["status"] = False
        data["last_seen"] = time.monotonic()
        self._store[branch_id] = data
        return True

    def get(self, branch_id: int) -> dict[str, Any] | None:
        """Tek branch telemetri verisi. Yoksa None."""
        return self._store.get(branch_id)

    def get_all(self) -> dict[int, dict[str, Any]]:
        """Tüm cache — dashboard fleet görünümü için."""
        return dict(self._store)

    def get_stale_branch_ids(self, timeout_seconds: float) -> list[int]:
        """
        Son heartbeat'i `timeout_seconds` sn'den eski olan branch ID'leri.
        Reaper döngüsü tarafından çağrılır.
        """
        cutoff = time.monotonic() - timeout_seconds
        return [
            bid
            for bid, data in self._store.items()
            if data.get("last_seen", 0.0) <= cutoff
            and data.get("status") is not False
        ]

    def evict(self, *, offline_ttl_seconds: float, max_branches: int) -> int:
        """
        Cache büyümesini sınırla.

        1) Offline ve TTL'i geçmiş kayıtları siler.
        2) Hâlâ limit üstündeyse en eski kayıtları siler.
        """
        removed = 0
        now = time.monotonic()

        if offline_ttl_seconds >= 0:
            offline_cutoff = now - offline_ttl_seconds
            stale_offline_ids = [
                bid
                for bid, data in self._store.items()
                if data.get("status") is False
                and data.get("last_seen", 0.0) <= offline_cutoff
            ]
            for bid in stale_offline_ids:
                self._store.pop(bid, None)
                removed += 1

        if max_branches > 0 and len(self._store) > max_branches:
            overflow = len(self._store) - max_branches
            oldest_ids = sorted(
                self._store.items(),
                key=lambda item: item[1].get("last_seen", 0.0),
            )[:overflow]
            for bid, _ in oldest_ids:
                self._store.pop(bid, None)
                removed += 1

        return removed

    def clear(self) -> None:
        """Test amaçlı — cache'i temizle."""
        self._store.clear()


# Module-level singleton — FloodProtector pattern'ı ile tutarlı
telemetry_cache = TelemetryCache()
