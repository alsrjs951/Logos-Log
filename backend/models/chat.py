from pydantic import BaseModel
from typing import List, Optional

class ChatHistoryItem(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    query: str
    history: Optional[List[ChatHistoryItem]] = []
    is_journal: Optional[bool] = False
    journal_id: Optional[str] = None

class ChatSource(BaseModel):
    id: str
    content: str
    content_ko: Optional[str] = None
    summary_ko: Optional[str] = None
    author: Optional[str] = None
    year: Optional[str] = None
    title: Optional[str] = None
    filename: Optional[str] = None
    section: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    chunk_id: Optional[str] = None
    chunk_index: Optional[int] = None
    language: Optional[str] = None
    text_quality: Optional[float] = None
    category: Optional[str] = None
    similarity: float

class ChatResponse(BaseModel):
    answer: str
    sources: List[ChatSource]
