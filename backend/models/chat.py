from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    query: str

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
