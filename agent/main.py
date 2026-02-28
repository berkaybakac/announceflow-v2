"""Agent Boot Sequence — Faz 3 Adim 1.

Blueprint 3B.2 standardi (Adim 1-3):
1. Logger kurulumu (en once)
2. CPU Serial oku (/proc/cpuinfo) -> logla (Lisans kontrolu Faz 4)
3. device_token.txt oku -> Yoksa ERROR + sonsuz bekleme (CRASH YASAK)
4. init_db() -> WAL + 4 tablo + APScheduler tablolari
5. APScheduler baslat

Kapsam disi (sonraki adimlar):
- HTTP Register (Adim 4)
- Manifest Sync (Adim 5-6)
- Ezan cache (Adim 7)
- MQTT (Adim 8-10)
"""

from __future__ import annotations

import asyncio
import logging
import platform
import signal
import sys

import aiofiles

from agent.core.database import close_db, init_db
from agent.core.logger import setup_logging
from agent.core.settings import agent_settings
from agent.scheduler import shutdown_scheduler, start_scheduler

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CPU Serial — Hardware Binding (Stub — Lisans kontrolu Faz 4)
# ---------------------------------------------------------------------------
async def _read_cpu_serial() -> str:
    """Raspberry Pi CPU Serial numarasini okur.

    /proc/cpuinfo icindeki 'Serial' satirini parse eder.
    Linux disinda veya okunamazsa 'UNKNOWN' dondurur.

    Faz 4'te bu deger lisans dosyasiyla karsilastirilacak.
    Simdilik sadece loglaniyor.
    """
    if platform.system() != "Linux":
        logger.info(
            "CPU Serial: Linux degil, atlanıyor",
            extra={"platform": platform.system()},
        )
        return "UNKNOWN"

    try:
        async with aiofiles.open("/proc/cpuinfo", mode="r") as f:
            content = await f.read()

        for line in content.splitlines():
            if line.strip().startswith("Serial"):
                serial = line.split(":")[-1].strip()
                logger.info(
                    "CPU Serial okundu",
                    extra={"serial": serial[-8:]},  # Son 8 hane (guvenlik)
                )
                return serial

        logger.warning("CPU Serial satirı bulunamadi (/proc/cpuinfo)")
        return "UNKNOWN"

    except OSError as exc:
        logger.warning(
            "CPU Serial okunamadi",
            extra={"error": str(exc)},
        )
        return "UNKNOWN"


# ---------------------------------------------------------------------------
# Device Token — Zero-Touch Provisioning
# ---------------------------------------------------------------------------
async def _wait_or_shutdown(
    shutdown_event: asyncio.Event,
    timeout_seconds: int,
) -> bool:
    """Timeout dolana kadar veya shutdown sinyali gelene kadar bekler.

    Returns:
        bool: True ise shutdown sinyali geldi, False ise timeout doldu.
    """
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=timeout_seconds)
        return True
    except asyncio.TimeoutError:
        return False


async def _read_device_token(shutdown_event: asyncio.Event) -> str | None:
    """Device token dosyasini okur.

    Dosya yoksa veya bossa:
    - ERROR logla
    - asyncio.sleep(60) ile sonsuz dongude bekle
    - Uygulamanin cokmesine ASLA izin verme

    Blueprint: 'Token yoksa hata logla, bekle.'
    """
    token_path = agent_settings.TOKEN_PATH

    while not shutdown_event.is_set():
        try:
            async with aiofiles.open(token_path, mode="r") as f:
                token = (await f.read()).strip()

            if not token:
                logger.error(
                    "Device token dosyasi bos",
                    extra={"path": token_path},
                )
                if await _wait_or_shutdown(shutdown_event, 60):
                    break
                continue

            logger.info(
                "Device token okundu",
                extra={"token_preview": f"{token[:8]}..."},
            )
            return token

        except FileNotFoundError:
            logger.error(
                "Device token dosyasi bulunamadi — bekleniyor",
                extra={"path": token_path},
            )
            if await _wait_or_shutdown(shutdown_event, 60):
                break

        except OSError as exc:
            logger.error(
                "Device token okunamadi — bekleniyor",
                extra={"path": token_path, "error": str(exc)},
            )
            if await _wait_or_shutdown(shutdown_event, 60):
                break

    logger.info("Device token beklemesi shutdown nedeniyle sonlandirildi")
    return None


# ---------------------------------------------------------------------------
# Boot Sequence
# ---------------------------------------------------------------------------
async def boot_sequence(shutdown_event: asyncio.Event) -> bool:
    """Agent boot islemi — sirasıyla calisir.

    Adim 1: Logger kurulumu
    Adim 2: CPU Serial oku (stub — Faz 4 lisans)
    Adim 3: Device token oku (yoksa sonsuz bekleme)
    Adim 4: init_db() — WAL + 4 tablo hazir
    Adim 5: APScheduler baslat
    """
    # --- Adim 1: Logger (HER SEYDEN ONCE) ---
    setup_logging()
    logger.info("=== Agent Boot Sequence basladi ===")

    # --- Adim 2: CPU Serial ---
    cpu_serial = await _read_cpu_serial()

    # --- Adim 3: Device Token (sonsuz bekleme olabilir) ---
    device_token = await _read_device_token(shutdown_event)
    if device_token is None:
        logger.info("Boot sequence shutdown nedeniyle yarida kesildi")
        return False

    # --- Adim 4: Database (WAL + 4 tablo) ---
    await init_db()

    # --- Adim 5: APScheduler ---
    await start_scheduler()

    logger.info(
        "=== Boot Sequence tamamlandi — Agent READY ===",
        extra={
            "cpu_serial": cpu_serial[-8:] if cpu_serial != "UNKNOWN" else "UNKNOWN",
            "token_preview": f"{device_token[:8]}...",
            "db_path": agent_settings.DB_PATH,
        },
    )
    return True


# ---------------------------------------------------------------------------
# Graceful Shutdown
# ---------------------------------------------------------------------------
async def _shutdown() -> None:
    """Agent'i guvenli sekilde kapatir."""
    logger.info("Agent kapatiliyor...")
    await shutdown_scheduler()
    await close_db()
    logger.info("Agent kapatildi")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> None:
    """Agent entrypoint. asyncio event loop'u baslatir."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    shutdown_event = asyncio.Event()

    def _request_shutdown(sig: signal.Signals) -> None:
        if shutdown_event.is_set():
            return
        logger.info("Shutdown sinyali alindi", extra={"signal": sig.name})
        shutdown_event.set()

    # --- Graceful shutdown signal handler ---
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda sig=sig: _request_shutdown(sig),
        )

    try:
        boot_completed = loop.run_until_complete(boot_sequence(shutdown_event))
        if boot_completed:
            # Boot tamamlandi — event loop shutdown sinyalini bekler.
            loop.run_until_complete(shutdown_event.wait())
    except KeyboardInterrupt:
        shutdown_event.set()
    finally:
        loop.run_until_complete(_shutdown())
        loop.close()


if __name__ == "__main__":
    main()
