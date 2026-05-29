from pydantic import BaseModel
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

class HistoryItem(BaseModel):
    role: str
    content: str

class AnalysisExtractRequest(BaseModel):
    history: List[HistoryItem]

class AnalysisExtractResponse(BaseModel):
    keyword: str
    insight: str
