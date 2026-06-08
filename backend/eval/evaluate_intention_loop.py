"""
insight→행동→결과 루프 로직 평가 (순수 함수).

due_intentions(pull 재질문 대상 선별)와 compute_intention_stats(후속 이행률·도움정도)의
정확성을 결정론적 케이스로 검증한다. LLM·DB 불필요.

주의: 후속 이행률을 '제품 효과'로 검증하려면 실제 재방문 사용자가 필요하다(유보).
여기서 검증하는 것은 '계산 로직이 옳은가'까지다.
실행: cd backend && python eval/evaluate_intention_loop.py
"""
import os
import sys
from datetime import datetime, timedelta

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from services.intention_loop import (  # noqa: E402
    due_intentions, compute_intention_stats,
    STATUS_OPEN, STATUS_REFLECTED, STATUS_DISMISSED, DUE_AFTER_DAYS,
)

checks = []


def check(name, cond):
    checks.append((name, bool(cond)))


def main():
    now = datetime(2026, 6, 8, 12, 0, 0)

    def made(days_ago, status=STATUS_OPEN, helpfulness=None, cid="c1"):
        return {
            "card_id": cid,
            "status": status,
            "created_at": (now - timedelta(days=days_ago)).isoformat(),
            "helpfulness": helpfulness,
        }

    # --- due_intentions ---
    items = [
        made(5),                                  # 열림·5일 전 → due
        made(DUE_AFTER_DAYS),                      # 정확히 임계 → due (<=)
        made(1),                                   # 열림·1일 전 → 아직 아님
        made(10, status=STATUS_REFLECTED),         # 이미 결과 기록 → 제외
        made(10, status=STATUS_DISMISSED),         # 접어둠 → 제외
    ]
    due = due_intentions(items, now=now)
    check("due: 열린 다짐 중 임계 이상만 (2개)", len(due) == 2)
    check("due: reflected/dismissed 제외", all(d["status"] == STATUS_OPEN for d in due))
    check("due: 오래된 순 정렬", due[0]["created_at"] <= due[1]["created_at"])

    no_due = due_intentions([made(1), made(2)], now=now)
    check("due: 임계 미만이면 빈 리스트", no_due == [])

    # --- compute_intention_stats ---
    stats_items = [
        made(9, status=STATUS_REFLECTED, helpfulness=5),
        made(9, status=STATUS_REFLECTED, helpfulness=3),
        made(9, status=STATUS_OPEN),
        made(9, status=STATUS_DISMISSED),          # 분모에서 제외돼야 함
    ]
    s = compute_intention_stats(stats_items)
    check("stats: total=4", s["total"] == 4)
    check("stats: reflected=2", s["reflected"] == 2)
    check("stats: open=1", s["open"] == 1)
    check("stats: dismissed=1", s["dismissed"] == 1)
    # follow_through = reflected / (reflected+open) = 2/3 (dismissed 제외)
    check("stats: follow_through=2/3 (dismissed 제외)",
          abs(s["follow_through_rate"] - 2 / 3) < 1e-9)
    check("stats: helpfulness_avg=4.0", abs(s["helpfulness_avg"] - 4.0) < 1e-9)
    check("stats: helpfulness_dist[5]=1 & [3]=1",
          s["helpfulness_dist"][5] == 1 and s["helpfulness_dist"][3] == 1)

    # 빈 입력
    empty = compute_intention_stats([])
    check("stats: 빈 입력이면 rate=None", empty["follow_through_rate"] is None)

    print("=" * 56)
    print("  insight→행동→결과 루프 로직 평가")
    print("=" * 56)
    for name, ok in checks:
        print(f"  {'✅' if ok else '❌'} {name}")
    passed = all(ok for _, ok in checks)
    print("\n  " + ("✅ PASS" if passed else "❌ FAIL") + f" — {sum(ok for _, ok in checks)}/{len(checks)}")
    print("=" * 56)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
