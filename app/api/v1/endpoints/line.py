"""LINE Webhook エンドポイント。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import get_line_webhook_service
from app.schemas.line import (
    LineWebhookErrorResponse,
    LineWebhookResponse,
)
from app.services.line_service import (
    HTTP_STATUS_OK,
    LINE_SIGNATURE_HEADER,
    LineWebhookService,
)

router = APIRouter(prefix="/line", tags=["line"])


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    response_model=LineWebhookResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": LineWebhookErrorResponse,
            "description": "Invalid LINE signature",
        },
    },
)
async def line_webhook(
    request: Request,
    service: Annotated[LineWebhookService, Depends(get_line_webhook_service)],
) -> LineWebhookResponse | JSONResponse:
    """Receive LINE webhook events without logging user message contents."""
    body = await request.body()
    signature = request.headers.get(LINE_SIGNATURE_HEADER)

    result = await service.process_webhook(body=body, signature=signature)
    if result.http_status_code == HTTP_STATUS_OK:
        return LineWebhookResponse(status=result.status)

    return JSONResponse(
        status_code=result.http_status_code,
        content={"detail": result.detail},
    )
