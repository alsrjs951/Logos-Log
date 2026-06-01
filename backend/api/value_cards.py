import os
import json
import datetime
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from models.value_cards import (
    ValueCardCreate, 
    ValueCardResponse, 
    AnalysisExtractRequest, 
    AnalysisExtractResponse
)
from api.deps import get_current_user
from db import get_db

router = APIRouter()

def serialize_value_card(doc) -> dict:
    """
    MongoDB 문서 객체를 Pydantic 모델에 호환되는 직렬화된 사전 객체로 변환합니다.
    """
    if not doc:
        return {}
    return {
        "id": str(doc["_id"]),
        "keyword": doc.get("keyword"),
        "insight": doc.get("insight"),
        "emotion": doc.get("emotion"),
        "user_id": doc.get("user_id"),
        "created_at": doc.get("created_at")
    }

@router.post("/value-cards/extract", response_model=AnalysisExtractResponse)
async def extract_value_card(
    request: AnalysisExtractRequest,
    current_user: dict = Depends(get_current_user)
):
    if not request.history:
        raise HTTPException(status_code=400, detail="대화 내역이 비어 있습니다.")
        
    try:
        # ChatOpenAI 초기화 (비스트리밍으로 빠르게 JSON 받아오기)
        llm = ChatOpenAI(
            model_name="gpt-3.5-turbo",
            temperature=0.3
        )
        
        system_prompt = (
            "당신은 심리 상담 대화록에서 사용자가 깨달은 가치와 삶의 태도를 분석하고 요약하는 전문가입니다.\n"
            "제공되는 대화 내역(사용자와 챗봇의 대화)을 읽고, 사용자가 대화 과정에서 최종적으로 도달한 '아하 모먼트(Aha-moment/깨달음의 순간)'를 찾아내어 가치 카드로 만드십시오.\n\n"
            "답변은 반드시 아래 형식을 갖춘 JSON 문자열 형태로만 출력해야 합니다. 다른 텍스트는 절대 포함하지 마십시오:\n"
            "{\n"
            "  \"keyword\": \"사용자가 깨달은 핵심 실존적 가치 (예: 자유, 책임, 관계, 용기, 수용, 태도, 연대 등 딱 한 단어로 작성)\",\n"
            "  \"insight\": \"사용자의 고민과 성찰을 반영하여, 이 대화를 통해 얻은 구체적인 깨달음과 삶의 태도를 1인칭 관점의 따뜻한 문장으로 한 줄 요약한 것\"\n"
            "}"
        )
        
        # 대화 히스토리를 텍스트로 가공
        history_text = ""
        for item in request.history:
            role_name = "사용자" if item.role == "user" else "상담가"
            history_text += f"{role_name}: {item.content}\n"
            
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"--- 대화 내역 ---\n{history_text}")
        ]
        
        response = await llm.ainvoke(messages)
        content_str = response.content.strip()
        
        # JSON 파싱 시도
        try:
            parsed_data = json.loads(content_str)
            return AnalysisExtractResponse(
                keyword=parsed_data.get("keyword", "성찰").strip(),
                insight=parsed_data.get("insight", "삶의 가치를 돌아보았습니다.").strip()
            )
        except json.JSONDecodeError:
            # LLM이 JSON 형식을 맞추지 못했을 경우 백업 문자열 파싱 시도
            if "keyword" in content_str and "insight" in content_str:
                import re
                kw_match = re.search(r'"keyword"\s*:\s*"([^"]+)"', content_str)
                is_match = re.search(r'"insight"\s*:\s*"([^"]+)"', content_str)
                return AnalysisExtractResponse(
                    keyword=kw_match.group(1) if kw_match else "성찰",
                    insight=is_match.group(1) if is_match else "대화에서 의미 있는 가치를 발견했습니다."
                )
            raise HTTPException(status_code=500, detail="AI가 올바른 JSON 형식으로 가치를 추출하지 못했습니다.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"가치 추출 오류: {str(e)}")

@router.post("/value-cards", response_model=ValueCardResponse)
async def create_value_card(card: ValueCardCreate, current_user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = current_user["id"]
    try:
        data = {
            "keyword": card.keyword,
            "insight": card.insight,
            "emotion": card.emotion,
            "user_id": user_id,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        result = db.value_cards.insert_one(data)
        data["_id"] = result.inserted_id
        
        return serialize_value_card(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터베이스 오류: {str(e)}")

@router.get("/value-cards", response_model=List[ValueCardResponse])
async def get_value_cards(current_user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = current_user["id"]
    try:
        cursor = db.value_cards.find({"user_id": user_id}).sort("created_at", -1)
        cards = [serialize_value_card(doc) for doc in cursor]
        return cards
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터베이스 오류: {str(e)}")
