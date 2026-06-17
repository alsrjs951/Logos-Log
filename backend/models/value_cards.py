from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

class ValueCardCreate(BaseModel):
    keyword: str
    insight: str
    emotion: Optional[str] = None

class ValueCardResponse(BaseModel):
    id: str
    keyword: str
    insight: str
    emotion: Optional[str] = None
    created_at: datetime
    # 종단 추적용 정규화 축(Schwartz). 레거시 카드는 None("미분류").
    canonical_value: Optional[str] = None
    canonical_confidence: Optional[float] = None
    canonical_method: Optional[str] = None

class HistoryItem(BaseModel):
    role: str
    content: str

class AnalysisExtractRequest(BaseModel):
    history: List[HistoryItem]

class AnalysisExtractResponse(BaseModel):
    keyword: str
    insight: str

class RecommendedExperimentResponse(BaseModel):
    status: str
    anchor_card_id: Optional[str] = None
    related_card_ids: List[str] = Field(default_factory=list)
    reason: str = ""
    experiment: str = ""
    reflection_question: str = ""
    source: str = "llm"
    cache_key: Optional[str] = None
