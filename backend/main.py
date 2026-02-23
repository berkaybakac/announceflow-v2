from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from backend.core.settings import settings
from backend.routers import auth_router, logs_router, media_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.MEDIA_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.MEDIA_TEMP_PATH).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

app.include_router(auth_router)
app.include_router(logs_router)
app.include_router(media_router)
