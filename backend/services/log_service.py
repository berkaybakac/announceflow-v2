import time
from collections import deque

from backend.models.log import LogEntry
from backend.repositories.log_repository import LogRepository
from backend.schemas.log import LogEntryCreate


class FloodProtector:
    """
    In-memory throttle — Loglama Anayasası Madde 5: Flood Protection.

    Aynı (branch_id, message) çifti saniyede >MAX_PER_SECOND kez gelirse
    loglama duraklatılır. Pencere geçtikten sonra sayaç sıfırlanır.
    """

    MAX_PER_SECOND: int = 10
    WINDOW_SECONDS: float = 1.0
    SWEEP_INTERVAL_SECONDS: float = 1.0

    def __init__(self) -> None:
        # (branch_id, message) -> monotonic timestamp deque
        self._counters: dict[tuple[int, str], deque[float]] = {}
        self._last_sweep_at: float = 0.0

    @staticmethod
    def _trim_bucket(bucket: deque[float], cutoff: float) -> None:
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

    def _sweep_expired_keys(self, now: float, cutoff: float) -> None:
        if now - self._last_sweep_at < self.SWEEP_INTERVAL_SECONDS:
            return

        stale_keys: list[tuple[int, str]] = []
        for key, bucket in self._counters.items():
            self._trim_bucket(bucket, cutoff)
            if not bucket:
                stale_keys.append(key)

        for key in stale_keys:
            del self._counters[key]

        self._last_sweep_at = now

    def is_allowed(self, branch_id: int, message: str) -> bool:
        """Verilen log kaydının flood limitini aşıp aşmadığını kontrol eder."""
        key = (branch_id, message)
        now = time.monotonic()
        cutoff = now - self.WINDOW_SECONDS

        # Global vacuum: tekrar hiç gelmeyen key'leri de temizler.
        self._sweep_expired_keys(now, cutoff)

        bucket = self._counters.get(key)
        if bucket is None:
            bucket = deque()
            self._counters[key] = bucket
        else:
            self._trim_bucket(bucket, cutoff)
            if not bucket:
                # Key'i RAM'den düşür, sadece gerektiğinde yeniden yarat.
                del self._counters[key]
                bucket = deque()
                self._counters[key] = bucket

        if len(bucket) >= self.MAX_PER_SECOND:
            return False

        bucket.append(now)
        return True


# Singleton — uygulama ömrü boyunca tek instance
_flood_protector = FloodProtector()


class LogService:
    """Log ingestion iş mantığı katmanı."""

    def __init__(self, repo: LogRepository) -> None:
        self.repo = repo
        self.flood = _flood_protector

    async def ingest(
        self,
        branch_id: int,
        entries: list[LogEntryCreate],
    ) -> int:
        """
        Log kayıtlarını flood kontrolünden geçirip veritabanına yazar.

        Returns:
            Kabul edilen (yazılan) log kaydı sayısı.
        """
        accepted: list[LogEntry] = []

        for entry in entries:
            if not self.flood.is_allowed(branch_id, entry.message):
                continue

            log = LogEntry(
                branch_id=branch_id,
                level=entry.level.value,
                message=entry.message,
                context=entry.context,
                created_at=entry.created_at,
            )
            accepted.append(log)

        if accepted:
            await self.repo.create_batch(accepted)

        return len(accepted)
