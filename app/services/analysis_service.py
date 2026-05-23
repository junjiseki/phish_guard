import asyncio
import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

RiskLevel = Literal["low", "medium", "high"]

ANALYSIS_PROMPT = """
あなたはフィッシング詐欺と詐欺SMS/メールの判定を支援するセキュリティ分析AIです。
添付画像内のSMSまたはメール文面を読み取り、危険度を判定してください。

判定ルール:
- 出力はJSONのみ。Markdown、説明文、コードブロックは含めない。
- risk_level は low / medium / high のいずれかにする。
- 判断できない、文面が読めない、根拠が不足している場合は medium にする。
- 「安全です」と断定しない。low の場合も「危険な特徴は限定的」程度に留める。
- summary は短い日本語の概要にする。
- reasons は最大3つ。画像内の本文を長く引用せず、根拠を要約する。
- actions は最大3つ。ユーザーが取るべき対応を具体的に書く。
- 画像内の個人情報、URL、電話番号、認証コード、本文全文を書き写さない。

JSON形式:
{
  "risk_level": "low | medium | high",
  "summary": "短い概要",
  "reasons": ["理由1", "理由2"],
  "actions": ["対応1", "対応2"]
}
""".strip()

FALLBACK_ANALYSIS = {
    "risk_level": "medium",
    "summary": "画像の内容を十分に判定できませんでした。",
    "reasons": [
        "AIの解析結果を検証できなかったため、危険度を中程度として扱います。",
    ],
    "actions": [
        "リンクや添付ファイルを開かず、送信元の公式アプリや公式サイトで確認してください。",
        "個人情報、認証コード、支払い情報を入力しないでください。",
    ],
}


class PhishingAnalysis(BaseModel):
    risk_level: RiskLevel
    summary: str = Field(min_length=1, max_length=200)
    reasons: list[str] = Field(default_factory=list, max_length=3)
    actions: list[str] = Field(default_factory=list, max_length=3)


class GeminiAnalysisService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def analyze_image(
        self,
        image_bytes: bytes,
        mime_type: str | None = None,
    ) -> PhishingAnalysis:
        if not image_bytes:
            return self._fallback()

        if not self.settings.gemini_api_key:
            logger.warning("Gemini API key is not configured")
            return self._fallback()

        request_body = self._build_request_body(
            image_bytes=image_bytes,
            mime_type=mime_type or detect_image_mime_type(image_bytes),
        )

        try:
            response_body = await asyncio.to_thread(self._post_to_gemini, request_body)
            response_text = extract_gemini_text(response_body)
            return PhishingAnalysis.model_validate_json(response_text)
        except (GeminiAnalysisError, ValidationError, json.JSONDecodeError) as exc:
            logger.warning("Gemini image analysis failed: %s", type(exc).__name__)
            return self._fallback()

    def _build_request_body(self, image_bytes: bytes, mime_type: str) -> dict[str, Any]:
        image_base64 = base64.b64encode(image_bytes).decode("ascii")

        return {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": ANALYSIS_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_base64,
                            },
                        },
                    ],
                },
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
                "responseJsonSchema": {
                    "type": "object",
                    "properties": {
                        "risk_level": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                        "summary": {"type": "string"},
                        "reasons": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 3,
                        },
                        "actions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 3,
                        },
                    },
                    "required": ["risk_level", "summary", "reasons", "actions"],
                },
            },
        }

    def _post_to_gemini(self, request_body: dict[str, Any]) -> dict[str, Any]:
        model = self.settings.gemini_model.removeprefix("models/")
        quoted_model = urllib.parse.quote(model, safe="")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quoted_model}:generateContent"
        )
        request = urllib.request.Request(
            url=url,
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.settings.gemini_api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.settings.request_timeout_seconds,
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise GeminiAnalysisError from exc

    def _fallback(self) -> PhishingAnalysis:
        return PhishingAnalysis.model_validate(FALLBACK_ANALYSIS)


class GeminiAnalysisError(Exception):
    pass


def detect_image_mime_type(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    return "image/jpeg"


def extract_gemini_text(response_body: dict[str, Any]) -> str:
    try:
        candidates = response_body["candidates"]
        parts = candidates[0]["content"]["parts"]
        text = parts[0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GeminiAnalysisError from exc

    if not isinstance(text, str) or not text.strip():
        raise GeminiAnalysisError

    return text


async def analyze_phishing_image(
    image_bytes: bytes,
    mime_type: str | None = None,
) -> PhishingAnalysis:
    service = GeminiAnalysisService()
    return await service.analyze_image(image_bytes=image_bytes, mime_type=mime_type)
