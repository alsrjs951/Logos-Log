import datetime
import json
from fastapi import APIRouter, HTTPException, Depends
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from api.deps import get_current_user
from services.encryption import decrypt
from db import get_db

router = APIRouter()


@router.get("/journals/weekly-report")
async def get_weekly_report(current_user: dict = Depends(get_current_user)):
    """
    최근 7일간의 일기를 기반으로 GPT가 주간 성찰 리포트를 생성합니다.
    - 감정 흐름 요약
    - 핵심 가치 키워드 3개
    - 다음 주 탐구 추천 질문 1개
    """
    db = get_db()
    user_id = current_user["id"]

    # 7일 전 날짜 계산
    seven_days_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).isoformat()

    try:
        cursor = db.journals.find(
            {"user_id": user_id, "created_at": {"$gte": seven_days_ago}},
            {"title": 1, "content": 1, "emotion": 1, "created_at": 1}
        ).sort("created_at", 1)

        journals = list(cursor)

        # 일기가 없는 경우
        if not journals:
            return {
                "has_data": False,
                "summary": None,
                "keywords": [],
                "next_question": None,
                "journal_count": 0,
            }

        # 일기 텍스트 가공
        journal_text = ""
        for j in journals:
            date_str = j.get("created_at", "")[:10]
            journal_text += (
                f"[{date_str}] 감정: {j.get('emotion', '?')} | "
                f"제목: {decrypt(j.get('title')) or '제목 없음'}\n"
                f"{decrypt(j.get('content')) or ''}\n\n"
            )

        system_prompt = (
            "당신은 긍정 심리학과 로고테라피 전문가입니다. "
            "사용자가 이번 주에 작성한 일기들을 읽고, 따뜻하고 통찰력 있는 주간 성찰 리포트를 작성해주세요.\n\n"
            "반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요:\n"
            "{\n"
            '  "summary": "이번 주 감정 흐름과 주요 성찰 내용을 2~3문장으로 따뜻하게 요약",\n'
            '  "keywords": ["핵심가치1", "핵심가치2", "핵심가치3"],\n'
            '  "next_question": "다음 주에 스스로에게 던져볼 소크라테스식 탐구 질문 1개"\n'
            "}"
        )

        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.5)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"--- 이번 주 일기 ---\n{journal_text}"),
        ]

        response = await llm.ainvoke(messages)
        content_str = response.content.strip()

        # JSON 파싱
        try:
            parsed = json.loads(content_str)
        except json.JSONDecodeError:
            # JSON 블록만 추출 시도
            import re
            match = re.search(r'\{.*\}', content_str, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
            else:
                raise HTTPException(status_code=500, detail="AI 응답 파싱 실패")

        return {
            "has_data": True,
            "summary": parsed.get("summary", ""),
            "keywords": parsed.get("keywords", []),
            "next_question": parsed.get("next_question", ""),
            "journal_count": len(journals),
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[report] weekly error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="주간 리포트 생성 중 오류가 발생했습니다.")
