"""
가치 택소노미 — Schwartz 기본가치 10개 (종단 추적의 '안정 축').

가치 카드의 자유 keyword("자유", "관계", "자율성"...)는 표면 라벨로 보존하되,
그 아래에 비교 가능한 canonical 값 1개를 부여한다(하이브리드). "자율성→관계성" 같은
추세는 이 canonical 축 위에서만 계산되므로, 같은 가치를 시간축으로 추적할 수 있다.

근거: Schwartz, S. H. (1992/2012). Theory of Basic Human Values — 교차문화로 검증된
10개 기본가치와, 인접/대립 구조를 이루는 4개 상위차원(circumplex). vision §4.2(인식론적
정직)에 따라, 임의 군집이 아니라 인용 가능한 검증된 체계를 축으로 삼는다.

분류 정책:
- LLM(gpt-4o-mini)으로 (keyword, insight) → 10개 중 1개 + confidence.
- confidence < CONFIDENCE_THRESHOLD 또는 분류 실패 시 canonical_value=None("미분류").
  권위를 지어내느니 "모른다"고 두는 편이 낫다(§4.2).
"""
import json
import os
from services.observability import log_event

# 상위차원(higher-order) — circumplex의 4분면
OPENNESS_TO_CHANGE = "openness_to_change"
SELF_ENHANCEMENT = "self_enhancement"
CONSERVATION = "conservation"
SELF_TRANSCENDENCE = "self_transcendence"

HIGHER_ORDER_LABELS_KR = {
    OPENNESS_TO_CHANGE: "변화 개방",
    SELF_ENHANCEMENT: "자기 고양",
    CONSERVATION: "보존",
    SELF_TRANSCENDENCE: "자기 초월",
}

# Schwartz 10 기본가치. angle 은 circumplex 표준 배열 순서(시각화 원형 배치에 재사용).
SCHWARTZ_VALUES = [
    {
        "key": "self_direction",
        "label_kr": "자기주도",
        "label_en": "Self-Direction",
        "definition_kr": "독립적인 사고와 행동, 자율성, 스스로 선택하고 탐구하며 창조하는 자유.",
        "higher_order": OPENNESS_TO_CHANGE,
        "angle": 0,
    },
    {
        "key": "stimulation",
        "label_kr": "자극",
        "label_en": "Stimulation",
        "definition_kr": "새로움, 도전, 흥분, 변화와 모험을 향한 추구.",
        "higher_order": OPENNESS_TO_CHANGE,
        "angle": 36,
    },
    {
        "key": "hedonism",
        "label_kr": "쾌락",
        "label_en": "Hedonism",
        "definition_kr": "즐거움, 감각적 만족, 삶을 누리는 기쁨.",
        "higher_order": SELF_ENHANCEMENT,
        "angle": 72,
    },
    {
        "key": "achievement",
        "label_kr": "성취",
        "label_en": "Achievement",
        "definition_kr": "역량을 발휘한 개인적 성공, 유능함, 사회적 기준에 따른 성과.",
        "higher_order": SELF_ENHANCEMENT,
        "angle": 108,
    },
    {
        "key": "power",
        "label_kr": "권력",
        "label_en": "Power",
        "definition_kr": "사회적 지위와 위신, 사람·자원에 대한 통제와 지배.",
        "higher_order": SELF_ENHANCEMENT,
        "angle": 144,
    },
    {
        "key": "security",
        "label_kr": "안전",
        "label_en": "Security",
        "definition_kr": "안전, 조화, 안정 — 자신·관계·사회의 지속과 평온.",
        "higher_order": CONSERVATION,
        "angle": 180,
    },
    {
        "key": "conformity",
        "label_kr": "순응",
        "label_en": "Conformity",
        "definition_kr": "규범·기대를 거스르지 않는 자제, 타인을 해치지 않는 절제.",
        "higher_order": CONSERVATION,
        "angle": 216,
    },
    {
        "key": "tradition",
        "label_kr": "전통",
        "label_en": "Tradition",
        "definition_kr": "관습·문화·종교가 부여한 가치와 신념의 존중과 수용.",
        "higher_order": CONSERVATION,
        "angle": 252,
    },
    {
        "key": "benevolence",
        "label_kr": "박애",
        "label_en": "Benevolence",
        "definition_kr": "가까운 사람들의 안녕을 지키고 돌보는 것 — 관계, 신의, 따뜻함.",
        "higher_order": SELF_TRANSCENDENCE,
        "angle": 288,
    },
    {
        "key": "universalism",
        "label_kr": "보편주의",
        "label_en": "Universalism",
        "definition_kr": "모든 사람과 자연의 안녕에 대한 이해, 관용, 보호 — 정의와 평등.",
        "higher_order": SELF_TRANSCENDENCE,
        "angle": 324,
    },
]

VALUE_BY_KEY = {v["key"]: v for v in SCHWARTZ_VALUES}
VALUE_KEYS = [v["key"] for v in SCHWARTZ_VALUES]

# confidence 가 이 값 미만이면 "미분류"(None)로 둔다.
CONFIDENCE_THRESHOLD = 0.5


def get_value(key):
    """canonical key → 정의 dict. 없으면 None."""
    return VALUE_BY_KEY.get(key)


def public_taxonomy():
    """프론트로 내려보낼 직렬화 가능한 택소노미(라벨·상위차원·각도)."""
    return [
        {
            "key": v["key"],
            "label_kr": v["label_kr"],
            "label_en": v["label_en"],
            "higher_order": v["higher_order"],
            "higher_order_kr": HIGHER_ORDER_LABELS_KR[v["higher_order"]],
            "angle": v["angle"],
        }
        for v in SCHWARTZ_VALUES
    ]


def _classification_prompt():
    lines = [
        "당신은 사용자의 성찰에서 드러난 핵심 가치를 Schwartz 기본가치 10개 중 하나로 분류하는 전문가입니다.",
        "아래 10개 가치 중, 주어진 키워드와 인사이트가 가장 잘 들어맞는 것 하나를 고르십시오.\n",
        "[가치 목록]",
    ]
    for v in SCHWARTZ_VALUES:
        lines.append(f"- {v['key']} ({v['label_kr']}): {v['definition_kr']}")
    lines += [
        "",
        "[출력 형식] 다른 텍스트 없이 아래 JSON만 출력하십시오:",
        '{ "value_key": "<위 key 중 하나, 또는 어느 것에도 맞지 않으면 \\"none\\">", '
        '"confidence": <0.0~1.0, 분류 확신도> }',
        "",
        "어느 가치에도 명확히 들어맞지 않으면 value_key 를 \"none\" 으로, "
        "확신이 낮으면 confidence 를 낮게 주십시오. 억지로 끼워 맞추지 마십시오.",
    ]
    return "\n".join(lines)


def classify_value(keyword, insight=""):
    """
    (keyword, insight) → (canonical_value: str|None, confidence: float, method: str)

    LLM(gpt-4o-mini)으로 분류. 실패하거나 confidence 가 임계 미만이면 (None, conf, ...).
    카드 저장을 막지 않도록 어떤 예외도 삼키고 (None, 0.0, "error") 를 반환한다.
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return None, 0.0, "empty"

    try:
        # 지연 임포트 — 이 모듈을 import 하는 것만으로 langchain 을 끌어오지 않도록.
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
        user_text = f"키워드: {keyword}\n인사이트: {(insight or '').strip()}"
        messages = [
            SystemMessage(content=_classification_prompt()),
            HumanMessage(content=user_text),
        ]
        resp = llm.invoke(messages)
        content = (resp.content or "").strip()

        # ```json 펜스가 붙어 오는 경우 제거
        if content.startswith("```"):
            content = content.strip("`")
            if content.lstrip().lower().startswith("json"):
                content = content.lstrip()[4:]

        data = json.loads(content)
        key = data.get("value_key")
        try:
            conf = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))

        if key not in VALUE_BY_KEY:
            # "none" 또는 알 수 없는 키 → 미분류
            return None, conf, "llm"
        if conf < CONFIDENCE_THRESHOLD:
            return None, conf, "llm"
        return key, conf, "llm"
    except Exception as e:  # noqa: BLE001 — 분류 실패가 카드 저장을 막아선 안 됨
        log_event("value_taxonomy_classify_error", level="warning", error_type=type(e).__name__)
        return None, 0.0, "error"
