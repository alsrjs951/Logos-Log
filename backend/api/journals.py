import os
from fastapi import APIRouter, HTTPException
from typing import List
from supabase import create_client, Client
from models.journals import JournalCreate, JournalResponse

router = APIRouter()

# Supabase Client 초기화
url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if url and key:
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    supabase_client: Client = create_client(url, key)
else:
    supabase_client = None

def get_db():
    if supabase_client is None:
        raise HTTPException(status_code=500, detail="Supabase 환경 변수가 설정되지 않았습니다.")
    return supabase_client

@router.post("/journals", response_model=JournalResponse)
def create_journal(journal: JournalCreate):
    db = get_db()
    try:
        data = {
            "title": journal.title,
            "content": journal.content,
            "emotion": journal.emotion
        }
        response = db.table("journals").insert(data).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="일기 저장에 실패했습니다. (응답 데이터 없음)")
            
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터베이스 오류: {str(e)}")

@router.get("/journals", response_model=List[JournalResponse])
def get_journals():
    db = get_db()
    try:
        response = db.table("journals").select("*").order("created_at", desc=True).execute()
        return response.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터베이스 오류: {str(e)}")
