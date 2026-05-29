from pydantic import BaseModel
from typing import List, Optional

class ChatHistoryItem(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    query: str
    history: Optional[List[ChatHistoryItem]] = []
    is_journal: Optional[bool] = False

class ChatSource(BaseModel):
    id: str
    content: str
    author: Optional[str] = None
    year: Optional[str] = None
    category: Optional[str] = None
    similarity: float

class ChatResponse(BaseModel):
    answer: str
    sources: List[ChatSource]
