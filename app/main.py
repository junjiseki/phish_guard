import logging

from fastapi import FastAPI

from app.api.routes.line import router as line_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Scam SMS and Phishing Mail Consultation AI",
    debug=settings.app_debug,
)

app.include_router(line_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Application started", extra={"app_env": settings.app_env})

