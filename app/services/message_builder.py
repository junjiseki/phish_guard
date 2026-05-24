from typing import Protocol

from app.schemas.analysis import RiskLevel


class AnalysisResult(Protocol):
    risk_level: RiskLevel
    summary: str
    reasons: list[str]
    actions: list[str]


RISK_HEADERS: dict[RiskLevel, str] = {
    "low": "念のため確認してください",
    "medium": "少し注意が必要です",
    "high": "危険な可能性があります",
}

DEFAULT_REASONS: dict[RiskLevel, list[str]] = {
    "low": ["今のところ強い危険な特徴は多くありません"],
    "medium": ["はっきり判断できないため注意が必要です"],
    "high": ["詐欺や偽の案内の可能性があります"],
}

DEFAULT_ACTIONS: dict[RiskLevel, list[str]] = {
    "low": [
        "心配な場合は公式アプリや公式窓口で確認してください",
        "不安なら家族に相談してください",
    ],
    "medium": [
        "URLや添付はすぐに開かないでください",
        "公式アプリや公式窓口で確認してください",
        "不安なら家族に相談してください",
    ],
    "high": [
        "URLや添付は開かないでください",
        "個人情報やお金の情報を入力しないでください",
        "家族や公式窓口に相談してください",
    ],
}


def build_line_reply(analysis: AnalysisResult) -> str:
    risk_level = analysis.risk_level
    header = RISK_HEADERS[risk_level]
    reasons = take_short_items(analysis.reasons, DEFAULT_REASONS[risk_level])
    actions = take_short_items(analysis.actions, DEFAULT_ACTIONS[risk_level])
    actions = ensure_consultation_action(actions, risk_level)

    return "\n".join(
        [
            f"{risk_icon(risk_level)} {header}",
            "",
            "理由：",
            *format_items(reasons),
            "",
            "対応：",
            *format_items(actions),
        ],
    )


def take_short_items(items: list[str], default_items: list[str]) -> list[str]:
    cleaned_items = [item.strip() for item in items if item.strip()]
    return (cleaned_items or default_items)[:3]


def ensure_consultation_action(actions: list[str], risk_level: RiskLevel) -> list[str]:
    if any(("家族" in action or "公式窓口" in action) for action in actions):
        return actions[:3]

    consultation_action = "家族や公式窓口に相談してください"
    if risk_level == "low":
        consultation_action = "不安なら家族や公式窓口に相談してください"

    if len(actions) >= 3:
        return [*actions[:2], consultation_action]

    return [*actions, consultation_action]


def format_items(items: list[str]) -> list[str]:
    return [f"・{item}" for item in items[:3]]


def risk_icon(risk_level: RiskLevel) -> str:
    if risk_level == "high":
        return "⚠️"
    if risk_level == "medium":
        return "⚠️"
    return "🔎"
