from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class ValueCardCreate(BaseModel):
    keyword: str
    insight: str

class ValueCardResponse(BaseModel):
    id: str
    keyword: str
    insight: str
    created_at: datetime

class HistoryItem(BaseModel):
    role: str
    content: str

class AnalysisExtractRequest(BaseModel):
    history: List[HistoryItem]

class AnalysisExtractResponse(BaseModel):
    keyword: str
    insight: str
