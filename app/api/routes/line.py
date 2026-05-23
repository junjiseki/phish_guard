from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.services.line_service import (
    LINE_SIGNATURE_HEADER,
    LineSignatureError,
    LineWebhookError,
    LineWebhookService,
)

router = APIRouter(prefix="/line", tags=["line"])


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def line_webhook(request: Request) -> dict[str, Any]:
    """Receive LINE webhook events without logging user message contents."""
    body = await request.body()
    signature = request.headers.get(LINE_SIGNATURE_HEADER)

    try:
        await LineWebhookService().handle_webhook(body=body, signature=signature)
    except LineSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid LINE signature",
        ) from exc
    except LineWebhookError:
        return {"status": "ok"}

    return {"status": "ok"}
