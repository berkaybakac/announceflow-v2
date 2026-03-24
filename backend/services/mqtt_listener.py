"""
MQTT Listener — Altyapı katmanı.

aiomqtt ile MQTT Broker'a bağlanır, status ve LWT topic'lerini dinler,
mesajları HeartbeatService'e yönlendirir.

Reaper döngüsü de burada tanımlanır: her MQTT_REAPER_INTERVAL_SECONDS
saniyede bir çalışır ve 3 dakikadır heartbeat gelmemiş branch'leri
offline yapar.

Bu modül FastAPI lifespan handler'ından asyncio.create_task() ile
başlatılır. Request döngüsünden bağımsız çalışır.
"""

import asyncio
import logging

import aiomqtt

from backend.core.settings import settings
from backend.services import heartbeat_service

logger = logging.getLogger(__name__)

_MESSAGE_PROCESSING_ERRORS = (RuntimeError, ValueError, TypeError, OSError)
_LISTENER_RECOVERABLE_ERRORS = (OSError, RuntimeError, ValueError, TypeError)
_REAPER_RECOVERABLE_ERRORS = (RuntimeError, ValueError, TypeError, OSError)


async def _dispatch_message(topic: str, payload: bytes) -> None:
    if topic.endswith("/status"):
        await heartbeat_service.handle_status_message(topic, payload)
        return
    if topic.endswith("/lwt"):
        await heartbeat_service.handle_lwt_message(topic)
        return
    logger.debug("Bilinmeyen topic: %s", topic)


async def mqtt_listener_loop() -> None:
    """
    Ana MQTT dinleme döngüsü.

    Bağlantı koparsa 5 sn bekleyip yeniden bağlanır (infinite reconnect).
    Graceful shutdown için asyncio.CancelledError yakalanır.
    """
    while True:
        try:
            logger.info(
                "MQTT Broker'a bağlanılıyor: %s:%d",
                settings.MQTT_BROKER_HOST,
                settings.MQTT_BROKER_PORT,
            )
            async with aiomqtt.Client(
                settings.MQTT_BROKER_HOST,
                settings.MQTT_BROKER_PORT,
            ) as client:
                await client.subscribe(settings.MQTT_TOPIC_STATUS)
                await client.subscribe(settings.MQTT_TOPIC_LWT)
                logger.info("MQTT Listener aktif — topic'ler dinleniyor.")

                async for message in client.messages:
                    topic = str(message.topic)
                    try:
                        await _dispatch_message(topic, message.payload)
                    except asyncio.CancelledError:
                        raise
                    except _MESSAGE_PROCESSING_ERRORS:
                        logger.exception("Mesaj işleme hatası: topic=%s", topic)

        except aiomqtt.MqttError as exc:
            logger.warning("MQTT bağlantı hatası: %s — 5 sn sonra yeniden deneniyor", exc)
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("MQTT Listener kapatılıyor (CancelledError).")
            break
        except _LISTENER_RECOVERABLE_ERRORS:
            logger.exception("MQTT Listener beklenmeyen hata — 5 sn sonra yeniden deneniyor")
            await asyncio.sleep(5)


async def reaper_loop() -> None:
    """
    Periyodik 'ölü' branch temizleme döngüsü.

    Her MQTT_REAPER_INTERVAL_SECONDS saniyede bir çalışır.
    3 dakikadır heartbeat gelmeyen branch'leri offline yapar.
    """
    logger.info(
        "Reaper döngüsü başlatıldı — interval=%d sn, timeout=%d sn",
        settings.MQTT_REAPER_INTERVAL_SECONDS,
        settings.MQTT_HEARTBEAT_TIMEOUT_SECONDS,
    )
    while True:
        try:
            await asyncio.sleep(settings.MQTT_REAPER_INTERVAL_SECONDS)
            await heartbeat_service.reap_stale_branches()
        except asyncio.CancelledError:
            logger.info("Reaper döngüsü kapatılıyor (CancelledError).")
            break
        except _REAPER_RECOVERABLE_ERRORS:
            logger.exception("Reaper döngüsü hatası")
