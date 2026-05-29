from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class JournalCreate(BaseModel):
    title: str
    content: str
    emotion: Optional[str] = "calm"

class JournalResponse(BaseModel):
    id: str
    title: str
    content: str
    emotion: Optional[str] = None
    created_at: datetime
