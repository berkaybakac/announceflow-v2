from fastapi import FastAPI

from backend.core.settings import settings
from backend.routers import auth_router

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

app.include_router(auth_router)
