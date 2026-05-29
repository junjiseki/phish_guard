import asyncio

from app.core.config import Settings
from app.services.analysis_service import GeminiAnalysisService, extract_gemini_text


def test_extract_gemini_text_and_parse_analysis_json() -> None:
    response_body = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": (
                                '{"risk_level":"high","summary":"危険な可能性",'
                                '"reasons":["急がせる内容"],'
                                '"actions":["URLを開かない"]}'
                            ),
                        },
                    ],
                },
            },
        ],
    }

    service = GeminiAnalysisService(Settings(GEMINI_API_KEY="dummy"))
    service._post_to_gemini = lambda request_body: response_body  # type: ignore[method-assign]

    result = asyncio.run(service.analyze_image(b"image-bytes", "image/png"))

    assert result.risk_level == "high"
    assert result.summary == "危険な可能性"
    assert result.reasons == ["急がせる内容"]
    assert result.actions == ["URLを開かない"]


def test_analysis_service_falls_back_when_json_is_invalid() -> None:
    response_body = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "not json"}],
                },
            },
        ],
    }

    service = GeminiAnalysisService(Settings(GEMINI_API_KEY="dummy"))
    service._post_to_gemini = lambda request_body: response_body  # type: ignore[method-assign]

    result = asyncio.run(service.analyze_image(b"image-bytes", "image/png"))

    assert result.risk_level == "medium"
    assert "判定できませんでした" in result.summary


def test_extract_gemini_text_returns_candidate_text() -> None:
    assert (
        extract_gemini_text(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": '{"risk_level":"low"}'}],
                        },
                    },
                ],
            },
        )
        == '{"risk_level":"low"}'
    )


def test_analysis_prompt_prioritizes_official_sender_email_domain() -> None:
    service = GeminiAnalysisService(Settings(GEMINI_API_KEY="dummy"))

    request_body = service._build_request_body(b"image-bytes", "image/png")
    prompt = request_body["contents"][0]["parts"][0]["text"]

    assert "表示名ではなくメールアドレスのドメインを重視する" in prompt
    assert "正規ドメインと" in prompt
    assert "一致する場合" in prompt
    assert "ポイント利用や割引で金額が" in prompt
    assert "異なるだけでは危険扱いしない" in prompt
