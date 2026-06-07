"""
기존 value_cards 에 Schwartz canonical_value 를 일괄 부여(backfill).

종단 추적 정규화 축을 도입하기 전 저장된 카드들은 canonical_value 가 없다. 이 스크립트가
keyword + (복호화한) insight 로 classify_value 를 호출해 채워 넣는다.

암호화 gotcha: insight 는 AES-GCM 암호문(enc:v1:...)이므로 반드시 decrypt() 후 분류한다.

실행(backend/ 에서):
    python scripts/backfill_canonical_values.py            # canonical 없는 카드만
    python scripts/backfill_canonical_values.py --all      # 전체 재분류(덮어쓰기)
    python scripts/backfill_canonical_values.py --dry-run  # 변경 없이 미리보기
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from db import get_db  # noqa: E402  (.env 로드 포함)
from services.encryption import decrypt  # noqa: E402
from services.value_taxonomy import classify_value  # noqa: E402


def main():
    redo_all = "--all" in sys.argv
    dry_run = "--dry-run" in sys.argv

    db = get_db()
    query = {} if redo_all else {"canonical_value": {"$in": [None, ""]}}
    # canonical_value 필드가 아예 없는 레거시 문서도 포함
    if not redo_all:
        query = {"$or": [{"canonical_value": {"$exists": False}}, {"canonical_value": None}]}

    cards = list(db.value_cards.find(query))
    print(f"대상 카드: {len(cards)}개 (mode={'all' if redo_all else 'missing-only'}, dry_run={dry_run})")

    updated = mapped = 0
    for doc in cards:
        keyword = doc.get("keyword", "")
        insight = decrypt(doc.get("insight", "")) or ""
        cv, conf, method = classify_value(keyword, insight)
        if cv:
            mapped += 1
        label = cv if cv else "미분류"
        print(f"  - '{keyword}' → {label} (conf={conf:.2f}, {method})")
        if not dry_run:
            db.value_cards.update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "canonical_value": cv,
                    "canonical_confidence": conf,
                    "canonical_method": method,
                }},
            )
            updated += 1

    print(f"\n완료: {updated}개 갱신, {mapped}개 분류 성공, {len(cards) - mapped}개 미분류"
          + (" (dry-run: 실제 변경 없음)" if dry_run else ""))


if __name__ == "__main__":
    main()
