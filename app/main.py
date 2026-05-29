import logging

from fastapi import FastAPI, Request

from app.api.v1.endpoints.line import router as line_router
from app.core.config import get_settings
from app.utils.logger import setup_logging

settings = get_settings()
setup_logging(
    app_env=settings.app_env,
    log_level=settings.app_log_level,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Scam SMS and Phishing Mail Consultation AI",
    debug=settings.app_debug,
)

app.include_router(line_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/callback")
async def callback(request: Request) -> dict[str, str]:
    body = await request.body()
    print(body.decode())
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Application started", extra={"app_env": settings.app_env})
