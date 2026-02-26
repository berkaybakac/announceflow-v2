"""AgentLogger — JSON Structured Logging + Flood Protection.

Anayasa Kurallari:
- print() YASAKTIR. Tum ciktilar bu modulden gecer.
- Format: JSON (timestamp, level, module, message).
- Sadece stdout — Docker json-file driver 30MB limitle rotate eder.
- Flood Protection: Ayni hata saniyede >10 kez gelirse throttle + ozet.

Kullanim:
    from agent.core.logger import setup_logging
    setup_logging()  # Boot sequence'de ilk cagrilan sey

    import logging
    logger = logging.getLogger(__name__)
    logger.info("Mesaj", extra={"key": "value"})
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Optional

from pythonjsonlogger.json import JsonFormatter as _BaseJsonFormatter

from agent.core.settings import agent_settings

# ---------------------------------------------------------------------------
# Flood Protection Filter
# ---------------------------------------------------------------------------
_MAX_ENTRIES = 256  # Throttle state dict max boyutu (~25KB)
_WINDOW_SEC = 1.0  # Zaman penceresi (saniye)
_THRESHOLD = 10  # Pencere basina izin verilen mesaj sayisi
_MSG_KEY_LEN = 128  # Mesaj hash'i icin kullanilan karakter sayisi


class FloodFilter(logging.Filter):
    """Token Bucket benzeri log throttle filtresi.

    Her log mesajinin ilk 128 karakterinden bir key turetir.
    Ayni key 1 saniye icinde 10'dan fazla gelirse:
      - Fazla mesajlari bastirir (suppress)
      - Pencere sonunda "Flood: Suppressed N messages" ozet logu basar.

    RAM kullanimi: ~100 byte / entry, max 256 entry = ~25KB.
    """

    def __init__(self) -> None:
        super().__init__()
        # key -> (window_start, count_in_window, suppressed_count)
        self._state: dict[str, list[float | int]] = {}
        self._lock = threading.RLock()

    def filter(self, record: logging.LogRecord) -> bool:
        """True donerse mesaj loglanir, False donerse bastirilir."""
        now = time.monotonic()
        key = self._make_key(record)
        emit_summary_count = 0

        with self._lock:
            entry = self._state.get(key)

            if entry is None:
                # Ilk kez gorulen mesaj
                self._state[key] = [now, 1, 0]
                self._maybe_evict()
                return True

            window_start, count, suppressed = (
                float(entry[0]),
                int(entry[1]),
                int(entry[2]),
            )

            # Pencere suresi doldu mu?
            if (now - window_start) > _WINDOW_SEC:
                # Onceki pencerenin ozetini lock disinda bas
                emit_summary_count = suppressed

                # Yeni pencere baslat
                entry[0] = now
                entry[1] = 1
                entry[2] = 0
                should_log = True
            else:
                # Pencere icindeyiz — sayaci artir
                entry[1] = count + 1

                if count + 1 <= _THRESHOLD:
                    should_log = True
                else:
                    # Esik asildi — bastir
                    entry[2] = suppressed + 1
                    should_log = False

        if emit_summary_count > 0:
            self._emit_summary(record, key, emit_summary_count)

        return should_log

    def _make_key(self, record: logging.LogRecord) -> str:
        """Log mesajindan throttle key'i turetir."""
        msg = record.getMessage()
        return f"{record.levelno}:{msg[:_MSG_KEY_LEN]}"

    def _emit_summary(
        self, record: logging.LogRecord, key: str, suppressed: int
    ) -> None:
        """Bastirilan mesajlarin ozetini loglar."""
        summary_logger = logging.getLogger("agent.flood")
        summary_logger.warning(
            "Flood: Suppressed %d identical messages",
            suppressed,
            extra={"throttled_key": key[:64]},
        )

    def _maybe_evict(self) -> None:
        """Dict cok buyuduyse en eski pencereleri temizler."""
        if len(self._state) <= _MAX_ENTRIES:
            return

        # En eski window_start'a sahip entry'leri sil
        items_snapshot = list(self._state.items())
        sorted_items = sorted(items_snapshot, key=lambda item: float(item[1][0]))
        to_remove = len(self._state) - _MAX_ENTRIES
        for key, _ in sorted_items[:to_remove]:
            self._state.pop(key, None)


# ---------------------------------------------------------------------------
# JSON Formatter
# ---------------------------------------------------------------------------
class AgentJsonFormatter(_BaseJsonFormatter):
    """Agent icin ozellestirilmis JSON formatter.

    Cikti ornegi:
    {"timestamp": "2026-02-25T12:00:00", "level": "INFO",
     "module": "database", "message": "init_db tamamlandi",
     "journal_mode": "wal"}
    """

    def add_fields(
        self,
        log_record: dict,
        record: logging.LogRecord,
        message_dict: dict,
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = self.formatTime(record)
        log_record["level"] = record.levelname
        log_record["module"] = record.module


# ---------------------------------------------------------------------------
# setup_logging — Boot sequence'de ilk cagirilir
# ---------------------------------------------------------------------------
_logging_configured = False


def setup_logging(level: Optional[str] = None) -> None:
    """Root logger'i JSON format + FloodFilter ile configure eder.

    Idempotent: Birden fazla kez cagirilsa bile tek handler eklenir.

    Args:
        level: Log seviyesi override. None ise settings.LOG_LEVEL kullanilir.
    """
    global _logging_configured

    if _logging_configured:
        return

    log_level = (level or agent_settings.LOG_LEVEL).upper()

    # --- Root logger ---
    root = logging.getLogger()
    root.setLevel(log_level)

    # --- Mevcut handler'lari temizle (double-init koruması) ---
    root.handlers.clear()

    # --- stdout handler + JSON formatter ---
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    formatter = AgentJsonFormatter(
        fmt="%(timestamp)s %(level)s %(module)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    # --- Flood Protection ---
    flood_filter = FloodFilter()
    handler.addFilter(flood_filter)

    root.addHandler(handler)

    # --- APScheduler ve SQLAlchemy loglarini sustur ---
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    _logging_configured = True

    logger = logging.getLogger(__name__)
    logger.info(
        "Logger baslatildi",
        extra={"level": log_level, "flood_threshold": _THRESHOLD},
    )
