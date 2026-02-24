import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI

from backend.core.settings import settings
from backend.routers import (
    auth_router,
    logs_router,
    manifest_router,
    media_router,
    schedules_router,
    telemetry_router,
)
from backend.services.mqtt_listener import mqtt_listener_loop, reaper_loop


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup — dizinler
    Path(settings.MEDIA_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.MEDIA_TEMP_PATH).mkdir(parents=True, exist_ok=True)

    # Startup — MQTT Heartbeat Monitor background tasks
    mqtt_task = asyncio.create_task(mqtt_listener_loop())
    reaper_task = asyncio.create_task(reaper_loop())

    yield

    # Shutdown — graceful cancel
    mqtt_task.cancel()
    reaper_task.cancel()
    with suppress(asyncio.CancelledError):
        await mqtt_task
        await reaper_task


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

app.include_router(auth_router)
app.include_router(logs_router)
app.include_router(manifest_router)
app.include_router(media_router)
app.include_router(schedules_router)
app.include_router(telemetry_router)

