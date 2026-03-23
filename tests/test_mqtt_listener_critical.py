import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services import mqtt_listener


class _MessageStream:
    def __init__(self, events):
        self._events = list(events)
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._events):
            raise asyncio.CancelledError
        event = self._events[self._index]
        self._index += 1
        if isinstance(event, BaseException):
            raise event
        return event


class _FakeClient:
    def __init__(self, events):
        self.messages = _MessageStream(events)
        self.subscribe = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_mqtt_listener_routes_status_and_lwt_messages() -> None:
    status_topic = "announceflow/istanbul/1/status"
    lwt_topic = "announceflow/istanbul/1/lwt"
    fake_client = _FakeClient(
        [
            SimpleNamespace(topic=status_topic, payload=b'{"is_online": true}'),
            SimpleNamespace(topic=lwt_topic, payload=b""),
        ]
    )

    with (
        patch(
            "backend.services.mqtt_listener.aiomqtt.Client",
            return_value=fake_client,
        ),
        patch(
            "backend.services.mqtt_listener.heartbeat_service.handle_status_message",
            new=AsyncMock(),
        ) as status_handler,
        patch(
            "backend.services.mqtt_listener.heartbeat_service.handle_lwt_message",
            new=AsyncMock(),
        ) as lwt_handler,
    ):
        await mqtt_listener.mqtt_listener_loop()

    status_handler.assert_awaited_once_with(status_topic, b'{"is_online": true}')
    lwt_handler.assert_awaited_once_with(lwt_topic)
    assert fake_client.subscribe.await_count == 2


@pytest.mark.asyncio
async def test_mqtt_listener_survives_handler_error_and_unknown_topic() -> None:
    status_topic = "announceflow/ankara/5/status"
    unknown_topic = "announceflow/ankara/5/metrics"
    lwt_topic = "announceflow/ankara/5/lwt"

    fake_client = _FakeClient(
        [
            SimpleNamespace(topic=status_topic, payload=b'{"bad": true}'),
            SimpleNamespace(topic=unknown_topic, payload=b"{}"),
            SimpleNamespace(topic=lwt_topic, payload=b""),
        ]
    )

    with (
        patch(
            "backend.services.mqtt_listener.aiomqtt.Client",
            return_value=fake_client,
        ),
        patch(
            "backend.services.mqtt_listener.heartbeat_service.handle_status_message",
            new=AsyncMock(side_effect=RuntimeError("parse error")),
        ) as status_handler,
        patch(
            "backend.services.mqtt_listener.heartbeat_service.handle_lwt_message",
            new=AsyncMock(),
        ) as lwt_handler,
        patch.object(mqtt_listener.logger, "exception", new=MagicMock()) as log_exc,
        patch.object(mqtt_listener.logger, "debug", new=MagicMock()) as log_debug,
    ):
        await mqtt_listener.mqtt_listener_loop()

    status_handler.assert_awaited_once_with(status_topic, b'{"bad": true}')
    lwt_handler.assert_awaited_once_with(lwt_topic)
    log_exc.assert_called_once()
    log_debug.assert_called_once_with("Bilinmeyen topic: %s", unknown_topic)


@pytest.mark.asyncio
async def test_mqtt_listener_reconnects_after_broker_error() -> None:
    second_client = _FakeClient([])
    mqtt_error = mqtt_listener.aiomqtt.MqttError("broker disconnected")

    with (
        patch(
            "backend.services.mqtt_listener.aiomqtt.Client",
            side_effect=[mqtt_error, second_client],
        ) as client_ctor,
        patch(
            "backend.services.mqtt_listener.asyncio.sleep",
            new=AsyncMock(),
        ) as sleep_mock,
    ):
        await mqtt_listener.mqtt_listener_loop()

    assert client_ctor.call_count == 2
    sleep_mock.assert_awaited_once_with(5)
