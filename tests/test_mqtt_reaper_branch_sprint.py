import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from backend.services import mqtt_listener


@pytest.mark.asyncio
async def test_reaper_loop_calls_reap_periodically() -> None:
    sleep_mock = AsyncMock(side_effect=[None, asyncio.CancelledError()])
    reap_mock = AsyncMock()

    with (
        patch.object(mqtt_listener.asyncio, "sleep", new=sleep_mock),
        patch.object(
            mqtt_listener.heartbeat_service,
            "reap_stale_branches",
            new=reap_mock,
        ),
    ):
        await mqtt_listener.reaper_loop()

    assert sleep_mock.await_args_list == [
        call(mqtt_listener.settings.MQTT_REAPER_INTERVAL_SECONDS),
        call(mqtt_listener.settings.MQTT_REAPER_INTERVAL_SECONDS),
    ]
    reap_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_reaper_loop_survives_reap_exception_and_continues() -> None:
    sleep_mock = AsyncMock(side_effect=[None, None, asyncio.CancelledError()])
    reap_mock = AsyncMock(side_effect=[RuntimeError("boom"), None])

    with (
        patch.object(mqtt_listener.asyncio, "sleep", new=sleep_mock),
        patch.object(
            mqtt_listener.heartbeat_service,
            "reap_stale_branches",
            new=reap_mock,
        ),
        patch.object(mqtt_listener.logger, "exception", new=MagicMock()) as log_exc,
    ):
        await mqtt_listener.reaper_loop()

    assert reap_mock.await_count == 2
    assert any(
        args and "reaper döngüsü hatası" in str(args[0]).lower()
        for args, _ in log_exc.call_args_list
    )


@pytest.mark.asyncio
async def test_reaper_loop_stops_cleanly_on_cancelled_error() -> None:
    sleep_mock = AsyncMock(side_effect=asyncio.CancelledError())

    with (
        patch.object(mqtt_listener.asyncio, "sleep", new=sleep_mock),
        patch.object(
            mqtt_listener.heartbeat_service,
            "reap_stale_branches",
            new=AsyncMock(),
        ) as reap_mock,
        patch.object(mqtt_listener.logger, "info", new=MagicMock()) as log_info,
    ):
        await mqtt_listener.reaper_loop()

    reap_mock.assert_not_awaited()
    assert any(
        args
        and "kapatılıyor" in str(args[0]).lower()
        and "cancel" in str(args[0]).lower()
        for args, _ in log_info.call_args_list
    )
