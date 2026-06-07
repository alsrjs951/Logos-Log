"""
insight→행동→결과 루프 — 순수 로직.

가치 카드(insight)에서 끝나지 않고, 사용자가 세운 '다짐(intention)'과 나중의 '결과
(outcome)'를 잇는다(vision §3의 진짜 차별점). API/DB와 분리한 순수 함수로 두어
오프라인 검증(eval/evaluate_intention_loop.py)이 같은 로직을 공유한다.

재질문은 pull-not-push(§6 반-engagement): '며칠 지난 열린 다짐'을 사용자가 돌아왔을 때
보여줄 후보로만 골라낸다 — 알림으로 들이밀지 않는다.
"""
from datetime import datetime, timedelta

# 다짐 후 이만큼 지나야 "돌아볼 다짐"으로 떠올린다(너무 이르게 채근하지 않도록).
DUE_AFTER_DAYS = 3

STATUS_OPEN = "open"
STATUS_REFLECTED = "reflected"
STATUS_DISMISSED = "dismissed"
VALID_STATUSES = {STATUS_OPEN, STATUS_REFLECTED, STATUS_DISMISSED}


def _parse(ts):
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str) and ts:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def due_intentions(intentions, now=None, min_age_days=DUE_AFTER_DAYS):
    """열린(open) 다짐 중 생성된 지 min_age_days 이상 지난 것을 오래된 순으로 반환.

    intentions: [{ "status", "created_at", ... }]
    pull 재질문 대상(사용자가 돌아왔을 때 보여줄 "돌아볼 다짐")을 고른다.
    """
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=min_age_days)
    due = []
    for it in intentions:
        if it.get("status") != STATUS_OPEN:
            continue
        created = _parse(it.get("created_at"))
        if created is None:
            continue
        # tz-aware/naive 혼용 방지: naive 로 통일
        if created.tzinfo is not None:
            created = created.replace(tzinfo=None)
        if created <= cutoff:
            due.append(it)
    due.sort(key=lambda it: _parse(it.get("created_at")) or datetime.max)
    return due


def compute_intention_stats(intentions):
    """후속 이행률·도움정도 통계(측정 지표).

    follow_through_rate = reflected / (reflected + open)  — dismissed 는 분모 제외
      (사용자가 의식적으로 접은 다짐까지 '실패'로 세면 채근 압박이 되어 §6에 반함).
    helpfulness 는 결과를 기록한 다짐의 1~5 평균/분포.
    """
    total = len(intentions)
    by_status = {STATUS_OPEN: 0, STATUS_REFLECTED: 0, STATUS_DISMISSED: 0}
    helpfulness_vals = []
    for it in intentions:
        st = it.get("status")
        if st in by_status:
            by_status[st] += 1
        h = it.get("helpfulness")
        if isinstance(h, (int, float)) and st == STATUS_REFLECTED:
            helpfulness_vals.append(int(h))

    denom = by_status[STATUS_REFLECTED] + by_status[STATUS_OPEN]
    follow_through_rate = (by_status[STATUS_REFLECTED] / denom) if denom else None

    dist = {i: 0 for i in range(1, 6)}
    for h in helpfulness_vals:
        if 1 <= h <= 5:
            dist[h] += 1
    helpfulness_avg = (sum(helpfulness_vals) / len(helpfulness_vals)) if helpfulness_vals else None

    return {
        "total": total,
        "open": by_status[STATUS_OPEN],
        "reflected": by_status[STATUS_REFLECTED],
        "dismissed": by_status[STATUS_DISMISSED],
        "follow_through_rate": follow_through_rate,
        "helpfulness_avg": helpfulness_avg,
        "helpfulness_dist": dist,
        "reflected_count": len(helpfulness_vals),
    }
