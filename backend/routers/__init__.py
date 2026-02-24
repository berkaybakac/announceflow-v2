from backend.routers.auth import router as auth_router
from backend.routers.logs import router as logs_router
from backend.routers.media import router as media_router
from backend.routers.telemetry import router as telemetry_router

__all__ = ["auth_router", "logs_router", "media_router", "telemetry_router"]

