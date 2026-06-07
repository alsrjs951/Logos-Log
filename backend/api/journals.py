import os
import datetime
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from models.journals import JournalCreate, JournalResponse
from api.deps import get_current_user
from services.encryption import encrypt, decrypt
from db import get_db

router = APIRouter()

def serialize_journal(doc) -> dict:
    """
    MongoDB 문서 객체를 Pydantic 모델에 호환되는 직렬화된 사전 객체로 변환합니다.
    """
    if not doc:
        return {}
    return {
        "id": str(doc["_id"]),
        "title": decrypt(doc.get("title")),
        "content": decrypt(doc.get("content")),
        "emotion": doc.get("emotion"),
        "user_id": doc.get("user_id"),
        "created_at": doc.get("created_at")
    }

@router.post("/journals", response_model=JournalResponse)
async def create_journal(journal: JournalCreate, current_user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = current_user["id"]
    try:
        created_at_val = journal.created_at.isoformat() if journal.created_at else datetime.datetime.utcnow().isoformat()
        
        data = {
            "title": encrypt(journal.title),
            "content": encrypt(journal.content),
            "emotion": journal.emotion,
            "user_id": user_id,
            "created_at": created_at_val
        }
        
        result = db.journals.insert_one(data)
        data["_id"] = result.inserted_id
        
        return serialize_journal(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터베이스 오류: {str(e)}")

@router.get("/journals", response_model=List[JournalResponse])
async def get_journals(current_user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = current_user["id"]
    try:
        # 생성일 내림차순 정렬 조회
        cursor = db.journals.find({"user_id": user_id}).sort("created_at", -1)
        journals = [serialize_journal(doc) for doc in cursor]
        return journals
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터베이스 오류: {str(e)}")

@router.get("/journals/summary")
async def get_journals_summary(current_user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = current_user["id"]
    try:
        # 본문을 제외한 ID, 제목, 감정 상태, 날짜만 투영(Projection) 조회
        cursor = db.journals.find(
            {"user_id": user_id},
            {"title": 1, "emotion": 1, "created_at": 1}
        ).sort("created_at", -1)
        
        summaries = []
        for doc in cursor:
            summaries.append({
                "id": str(doc["_id"]),
                "title": decrypt(doc.get("title")),
                "emotion": doc.get("emotion"),
                "created_at": doc.get("created_at")
            })
        return summaries
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터베이스 오류: {str(e)}")

@router.delete("/journals/{journal_id}")
async def delete_journal(journal_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = current_user["id"]
    from bson import ObjectId
    try:
        try:
            journal_oid = ObjectId(journal_id)
        except Exception:
            raise HTTPException(status_code=400, detail="유효하지 않은 일기 ID 포맷입니다.")
            
        # 1. 일기 조회 및 소유권 확인
        journal = db.journals.find_one({"_id": journal_oid})
        if not journal:
            raise HTTPException(status_code=404, detail="해당 일기를 찾을 수 없습니다.")
        if journal.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="해당 일기를 삭제할 권한이 없습니다.")
            
        # 2. 일기 삭제
        db.journals.delete_one({"_id": journal_oid})
        
        # 3. 해당 일기에 속한 모든 chat_messages 캐시(대화 기록) 연쇄 삭제
        db.chat_messages.delete_many({"journal_id": journal_id})
        
        return {"status": "success", "message": "일기 및 대화 내역이 연쇄 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터베이스 오류: {str(e)}")

