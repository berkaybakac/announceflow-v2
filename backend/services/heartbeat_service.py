"""
Heartbeat Service — İş mantığı katmanı.

MQTT mesajlarını parse eder, telemetri cache'ini günceller
ve veritabanında online/offline durumunu yönetir.

KRİTİK: Bu servis Background Task içinde çalışır.
FastAPI request döngüsü dışında olduğu için Depends(get_db) KULLANMAZ.
Kendi session'larını async_session_factory üzerinden açar/kapatır.
"""

import json
import logging
import re
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from backend.core.database import async_session_factory
from backend.core.settings import settings
from backend.repositories.branch_repository import BranchRepository
from backend.services.telemetry_cache import telemetry_cache

logger = logging.getLogger(__name__)
_DB_RECOVERABLE_ERRORS = (SQLAlchemyError, OSError, RuntimeError)

# Topic format: announceflow/{tenant}/{branch_id}/status (veya /lwt)
# branch_id integer'a parse edilir, tenant şimdilik kullanılmaz (single-tenant).
_TOPIC_PATTERN = re.compile(r"^announceflow/([^/]+)/(\d+)/(status|lwt)$")


def parse_topic(topic: str) -> tuple[str, int, str] | None:
    """
    MQTT topic'ini parse et.

    Returns:
        (tenant, branch_id, message_type) veya geçersizse None.
    """
    match = _TOPIC_PATTERN.match(topic)
    if match is None:
        return None
    tenant = match.group(1)
    branch_id = int(match.group(2))
    msg_type = match.group(3)
    return tenant, branch_id, msg_type


def parse_payload(raw: bytes | str) -> dict[str, Any] | None:
    """JSON payload'ı güvenli şekilde parse et."""
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            logger.warning("Geçersiz telemetri payload: JSON object bekleniyor")
            return None
        return loaded
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Geçersiz telemetri payload: %s", exc)
        return None


async def _set_online_status_with_db(
    branch_id: int,
    is_online: bool,
    log_message: str,
) -> bool | None:
    async with async_session_factory() as session:
        try:
            repo = BranchRepository(session)
            updated = await repo.set_online_status(branch_id, is_online=is_online)
            await session.commit()
            return updated
        except _DB_RECOVERABLE_ERRORS:
            await session.rollback()
            logger.exception(log_message, branch_id)
            return None


async def handle_status_message(topic: str, raw_payload: bytes | str) -> None:
    """
    Status topic'inden gelen heartbeat mesajını işle.

    1. Topic'ten branch_id parse et
    2. JSON payload'ı parse et
    3. Cache'i güncelle
    4. DB'de is_online=True yap
    """
    parsed = parse_topic(topic)
    if parsed is None:
        logger.warning("Geçersiz status topic: %s", topic)
        return

    _, branch_id, _ = parsed
    parsed_payload = parse_payload(raw_payload)
    payload: dict[str, Any] = parsed_payload or {}

    # DB'de online olarak işaretle
    updated = await _set_online_status_with_db(
        branch_id=branch_id,
        is_online=True,
        log_message="DB is_online güncellemesi başarısız: branch=%d",
    )
    if updated is None:
        return

    # Bilinmeyen branch cache'e alınmaz (RAM büyümesi ve spoofing koruması).
    if not updated:
        logger.warning("Bilinmeyen branch status mesajı ignore edildi: branch=%d", branch_id)
        return

    # In-Memory Cache güncelle (DB'ye telemetri YAZILMAZ)
    telemetry_cache.update(
        branch_id,
        payload,
        max_string_length=settings.MQTT_TELEMETRY_MAX_STRING_LENGTH,
        force_status=True,
    )


async def handle_lwt_message(topic: str) -> None:
    """
    LWT topic'inden gelen 'cihaz koptu' mesajını işle.

    1. Topic'ten branch_id parse et
    2. DB'de is_online=False yap
    3. Cache'de offline işaretle
    """
    parsed = parse_topic(topic)
    if parsed is None:
        logger.warning("Geçersiz LWT topic: %s", topic)
        return

    _, branch_id, _ = parsed

    # DB'de offline
    updated = await _set_online_status_with_db(
        branch_id=branch_id,
        is_online=False,
        log_message="DB LWT güncellemesi başarısız: branch=%d",
    )
    if updated is None:
        return

    # Bilinmeyen branch için cache entry açma.
    if not updated:
        logger.warning("Bilinmeyen branch LWT mesajı ignore edildi: branch=%d", branch_id)
        return

    # Cache'de offline (branch DB'de doğrulandı).
    telemetry_cache.mark_offline(branch_id, create_if_missing=True)


async def reap_stale_branches() -> int:
    """
    3 dakikadır heartbeat gelmemiş branch'leri offline yap.

    Belt & suspenders: LWT güvenilir olmayabilir (broker restart vb.),
    bu yüzden süre aşımı ile de kontrol ediyoruz.

    Returns:
        Offline yapılan branch sayısı.
    """
    stale_ids = telemetry_cache.get_stale_branch_ids(
        settings.MQTT_HEARTBEAT_TIMEOUT_SECONDS,
    )
    count = 0

    if stale_ids:
        # Cache'de offline işaretle
        for bid in stale_ids:
            telemetry_cache.mark_offline(bid)

        # DB'de toplu offline
        async with async_session_factory() as session:
            try:
                repo = BranchRepository(session)
                count = await repo.set_bulk_offline(stale_ids)
                await session.commit()
                logger.info(
                    "Reaper: %d branch offline yapıldı (stale IDs: %s)",
                    count,
                    stale_ids,
                )
            except _DB_RECOVERABLE_ERRORS:
                await session.rollback()
                logger.exception("Reaper DB güncellemesi başarısız")
                count = 0

    evicted = telemetry_cache.evict(
        offline_ttl_seconds=settings.MQTT_TELEMETRY_OFFLINE_TTL_SECONDS,
        max_branches=settings.MQTT_TELEMETRY_CACHE_MAX_BRANCHES,
    )
    if evicted:
        logger.info("Reaper eviction: %d cache kaydı silindi", evicted)

    return count
