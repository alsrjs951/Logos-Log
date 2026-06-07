"""
가치 변화(추세) 계산 — 순수 함수.

API(GET /value-cards/trends)와 오프라인 평가(eval/evaluate_drift.py)가 같은 로직을
공유하도록 HTTP/DB와 분리한 순수 함수로 둔다. 입력은 가치카드의 (canonical_value,
created_at) 목록뿐이며, insight 본문은 읽지 않는다(복호화 불필요·프라이버시 최소노출).

핵심 원칙(vision §4.2 / §3): 데이터가 부족하거나 변화가 미미하면 추세를 단언하지 않는다.
'예쁜 그래프'와의 차별점은 바로 이 과잉 정밀 방지(flat 궤적엔 "변화 없음"이라 말함)다.
"""
from collections import Counter, defaultdict
from datetime import datetime
from math import comb

from services.value_taxonomy import VALUE_BY_KEY, HIGHER_ORDER_LABELS_KR

# 충분성/유의성 임계값
MIN_CARDS = 8          # 이만큼 카드가 쌓여야 변화를 말한다
MIN_MONTHS = 2         # 최소 2개 구간(월)에 걸쳐 있어야 추세
SHIFT_THRESHOLD = 0.15  # then→now 비중 변화가 이 이상이어야(크기 조건)
ALPHA = 0.10            # Fisher 정확검정 유의수준(소표본이라 다소 관대)


def _fisher_2x2_p(a, b, c, d):
    """2x2 분할표의 양측 Fisher 정확검정 p값(순수 파이썬, 의존성 없음).

    소표본에서 비중 변화가 표집 잡음으로 설명되는지 검정한다 — 카드 하나가 임계를
    넘겨 '변화'를 단언하는 오탐(과잉 정밀)을 막는 핵심 장치(§3/§4.2).
    """
    r1, r2 = a + b, c + d
    c1, c2 = a + c, b + d
    n = r1 + r2
    if n == 0 or r1 == 0 or r2 == 0 or c1 == 0 or c2 == 0:
        return 1.0

    def hyp(x):
        return comb(c1, x) * comb(c2, r1 - x) / comb(n, r1)

    p_obs = hyp(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    p = sum(px for x in range(lo, hi + 1) if (px := hyp(x)) <= p_obs + 1e-12)
    return min(1.0, p)


def _month_key(created_at):
    """ISO 문자열 또는 datetime → 'YYYY-MM'. 파싱 실패 시 None."""
    if isinstance(created_at, datetime):
        return f"{created_at.year:04d}-{created_at.month:02d}"
    if isinstance(created_at, str) and created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return f"{dt.year:04d}-{dt.month:02d}"
        except ValueError:
            return None
    return None


def _distribution(cards):
    """canonical_value 비중(매핑된 카드만 분모). 반환: {key: proportion}, mapped_count."""
    counts = Counter(c.get("canonical_value") for c in cards if c.get("canonical_value") in VALUE_BY_KEY)
    total = sum(counts.values())
    if total == 0:
        return {}, 0
    return {k: counts[k] / total for k in counts}, total


def _label(key):
    v = VALUE_BY_KEY.get(key)
    return v["label_kr"] if v else key


def compute_trends(cards, min_cards=MIN_CARDS, min_months=MIN_MONTHS,
                   shift_threshold=SHIFT_THRESHOLD):
    """
    cards: [{ "canonical_value": str|None, "created_at": str|datetime }, ...] (시간순 무관)

    반환 dict:
      total_cards, mapped_cards, unmapped_count, distinct_months,
      insufficient(bool), min_cards, min_months,
      timeline: [{month, counts:{key:int}, total}],  (월 오름차순)
      then_vs_now: { then:{distribution,count}, now:{distribution,count},
                     significant(bool), top_shift:{from,to,from_label,to_label,
                                                    from_delta,to_delta}|None },
      summary: str   (항상 정직한 한 문장; 부족/무변화도 그렇게 말함)
    """
    cards = list(cards or [])
    total_cards = len(cards)

    # 시간순 정렬 (created_at 없는 것은 뒤로)
    def _sort_key(c):
        ca = c.get("created_at")
        if isinstance(ca, datetime):
            return ca.isoformat()
        return ca or ""

    ordered = sorted(cards, key=_sort_key)

    # 월별 타임라인
    month_counts = defaultdict(Counter)
    for c in ordered:
        mk = _month_key(c.get("created_at"))
        cv = c.get("canonical_value")
        if mk and cv in VALUE_BY_KEY:
            month_counts[mk][cv] += 1
    timeline = [
        {"month": m, "counts": dict(month_counts[m]), "total": sum(month_counts[m].values())}
        for m in sorted(month_counts.keys())
    ]
    distinct_months = len(timeline)

    mapped_cards = sum(1 for c in ordered if c.get("canonical_value") in VALUE_BY_KEY)
    unmapped_count = total_cards - mapped_cards

    insufficient = (mapped_cards < min_cards) or (distinct_months < min_months)

    # then vs now: 매핑된 카드를 시간순 반으로 분할
    mapped_ordered = [c for c in ordered if c.get("canonical_value") in VALUE_BY_KEY]
    half = len(mapped_ordered) // 2
    then_cards = mapped_ordered[:half]
    now_cards = mapped_ordered[half:]
    then_dist, then_n = _distribution(then_cards)
    now_dist, now_n = _distribution(now_cards)

    significant = False
    top_shift = None
    p_value = None
    if not insufficient and then_n > 0 and now_n > 0:
        keys = set(then_dist) | set(now_dist)
        deltas = {k: now_dist.get(k, 0.0) - then_dist.get(k, 0.0) for k in keys}
        rising_key = max(deltas, key=lambda k: deltas[k])
        falling_key = min(deltas, key=lambda k: deltas[k])
        # 크기 조건: 가장 오른 가치/내린 가치가 임계 이상 움직였는가
        magnitude_ok = (deltas[rising_key] >= shift_threshold and
                        deltas[falling_key] <= -shift_threshold)
        if magnitude_ok:
            # 통계 조건: from↔to 구성이 then/now 사이에 유의하게 달라졌는가(Fisher).
            then_from = sum(1 for c in then_cards if c.get("canonical_value") == falling_key)
            then_to = sum(1 for c in then_cards if c.get("canonical_value") == rising_key)
            now_from = sum(1 for c in now_cards if c.get("canonical_value") == falling_key)
            now_to = sum(1 for c in now_cards if c.get("canonical_value") == rising_key)
            p_value = _fisher_2x2_p(then_from, then_to, now_from, now_to)
            if p_value < ALPHA:
                significant = True
                top_shift = {
                    "from": falling_key,
                    "to": rising_key,
                    "from_label": _label(falling_key),
                    "to_label": _label(rising_key),
                    "from_delta": round(deltas[falling_key], 3),
                    "to_delta": round(deltas[rising_key], 3),
                    "p_value": round(p_value, 4),
                }

    then_vs_now = {
        "then": {"distribution": {k: round(v, 3) for k, v in then_dist.items()}, "count": then_n},
        "now": {"distribution": {k: round(v, 3) for k, v in now_dist.items()}, "count": now_n},
        "significant": significant,
        "top_shift": top_shift,
    }

    summary = _build_summary(insufficient, mapped_cards, min_cards, significant, top_shift,
                             then_dist, now_dist)

    return {
        "total_cards": total_cards,
        "mapped_cards": mapped_cards,
        "unmapped_count": unmapped_count,
        "distinct_months": distinct_months,
        "insufficient": insufficient,
        "min_cards": min_cards,
        "min_months": min_months,
        "timeline": timeline,
        "then_vs_now": then_vs_now,
        "summary": summary,
    }


def _build_summary(insufficient, mapped_cards, min_cards, significant, top_shift,
                   then_dist, now_dist):
    """결정론적·정직한 한 문장. LLM을 쓰지 않아 환각 없이 테스트 가능."""
    if insufficient:
        return (f"아직 변화를 말하기엔 데이터가 부족합니다 "
                f"(분류된 카드 {mapped_cards}개 / 최소 {min_cards}개 필요).")
    if not significant or not top_shift:
        return "최근까지 핵심 가치의 뚜렷한 이동은 보이지 않습니다 — 비교적 일관된 흐름입니다."
    from_pct_then = round(then_dist.get(top_shift["from"], 0.0) * 100)
    from_pct_now = round(now_dist.get(top_shift["from"], 0.0) * 100)
    to_pct_then = round(then_dist.get(top_shift["to"], 0.0) * 100)
    to_pct_now = round(now_dist.get(top_shift["to"], 0.0) * 100)
    return (f"최근으로 올수록 '{top_shift['from_label']}' 비중이 {from_pct_then}%→{from_pct_now}%로 줄고, "
            f"'{top_shift['to_label']}'이(가) {to_pct_then}%→{to_pct_now}%로 늘었습니다. "
            f"단, 카드 {mapped_cards}개에 기반한 잠정적 관찰입니다.")
