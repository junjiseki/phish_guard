from app.schemas.analysis import PhishingAnalysis
from app.services.message_builder import build_line_reply


def test_build_line_reply_changes_message_by_risk_level() -> None:
    low_reply = build_line_reply(
        PhishingAnalysis(
            risk_level="low",
            summary="危険な特徴は限定的です",
            reasons=["不自然な点は少なめです"],
            actions=["公式アプリで確認してください"],
        ),
    )
    medium_reply = build_line_reply(
        PhishingAnalysis(
            risk_level="medium",
            summary="注意が必要です",
            reasons=["急がせる内容です"],
            actions=["URLはすぐ押さないでください"],
        ),
    )
    high_reply = build_line_reply(
        PhishingAnalysis(
            risk_level="high",
            summary="危険な可能性があります",
            reasons=["銀行を装っている可能性があります"],
            actions=["URLは押さないでください"],
        ),
    )

    assert "安全レベル: 高" in low_reply
    assert "安全な可能性が高いです" in low_reply
    assert "完全に安全" not in low_reply
    assert "対応：" not in low_reply
    assert "安全レベル: 中" in medium_reply
    assert "少し注意が必要です" in medium_reply
    assert "安全レベル: 低" in high_reply
    assert "危険な可能性があります" in high_reply
    assert "URLは押さないでください" in high_reply
    assert "家族" not in low_reply
    assert "家族" in medium_reply
    assert "家族" in high_reply


def test_build_line_reply_limits_reasons_and_actions_to_three() -> None:
    reply = build_line_reply(
        PhishingAnalysis(
            risk_level="high",
            summary="危険な可能性があります",
            reasons=["理由1", "理由2", "理由3"],
            actions=["対応1", "対応2", "対応3"],
        ),
    )

    assert reply.count("・理由") == 3
    assert "家族や公式窓口に相談してください" in reply
    assert "対応3" not in reply
