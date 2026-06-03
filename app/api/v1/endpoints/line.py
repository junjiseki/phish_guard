"""LINE Webhook エンドポイント。"""

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.schemas.line import LineWebhookResponse
from app.services.line_service import LINE_SIGNATURE_HEADER, LineWebhookService

router = APIRouter(prefix="/line", tags=["line"])


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    response_model=LineWebhookResponse,
)
async def line_webhook(request: Request) -> LineWebhookResponse | JSONResponse:
    """Receive LINE webhook events without logging user message contents."""
    body = await request.body()
    signature = request.headers.get(LINE_SIGNATURE_HEADER)

    result = await LineWebhookService().process_webhook(body=body, signature=signature)
    if result.http_status_code == status.HTTP_200_OK:
        return LineWebhookResponse(status=result.status)

    return JSONResponse(
        status_code=result.http_status_code,
        content={"detail": result.detail},
    )
