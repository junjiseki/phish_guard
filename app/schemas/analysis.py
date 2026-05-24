"""フィッシング解析結果の Pydantic スキーマ。"""

from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["low", "medium", "high"]


class PhishingAnalysis(BaseModel):
    """Gemini API による画像解析結果。"""

    risk_level: RiskLevel
    summary: str = Field(min_length=1, max_length=200)
    reasons: list[str] = Field(default_factory=list, max_length=3)
    actions: list[str] = Field(default_factory=list, max_length=3)
