from pydantic import BaseModel, Field
from typing import Optional


class IntentionCreate(BaseModel):
    card_id: str                      # 이 다짐이 따라 나온 가치 카드(insight)
    intention: str                    # "이번 주엔 거절을 한 번 해보겠다"


class IntentionReflect(BaseModel):
    outcome: str                      # "해보니 어땠나" — 실제 결과
    helpfulness: Optional[int] = Field(default=None, ge=1, le=5)  # 그 선택이 도움이 됐나(1~5)


class IntentionResponse(BaseModel):
    id: str
    card_id: str
    intention: str
    status: str                       # open | reflected | dismissed
    created_at: str
    outcome: Optional[str] = None
    outcome_logged_at: Optional[str] = None
    helpfulness: Optional[int] = None
    # 돌아볼 다짐 표시용(연결된 카드의 표면 라벨) — 선택적으로 채워진다
    card_keyword: Optional[str] = None
    card_canonical_value: Optional[str] = None
