from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class JournalCreate(BaseModel):
    title: str
    content: str
    emotion: Optional[str] = "calm"
    created_at: Optional[datetime] = None

class JournalResponse(BaseModel):
    id: str
    title: str
    content: str
    emotion: Optional[str] = None
    created_at: datetime
