"""
합성 가치 궤적 생성기 — 변화 감지(evaluate_drift.py) 평가용.

실사용자 종단 데이터가 아직 없으므로(현 DB: 카드 1건), '정답을 아는' 합성 궤적을 만들어
compute_trends 의 변화 감지를 ≥30 표본으로 검증한다. LLM·DB 불필요, 결정론적(seed 고정).

세 종류:
- clear_drift: from_key → to_key 로 분명히 이동(검출되어야 함)
- flat: 안정적 흐름(검출되면 안 됨 — 과잉 정밀/오탐 가드)
- noisy: 뚜렷한 추세 없는 잡음(강한 단언이 나오면 안 됨)
"""
import random

from services.value_taxonomy import VALUE_KEYS


def _timestamps(n, months, start_year=2026, start_month=1):
    """n개 카드를 months개월에 걸쳐 시간순으로 분포시킨 ISO 타임스탬프."""
    out = []
    for i in range(n):
        # i 번째 카드가 속할 월(0..months-1)
        m_idx = min(months - 1, int(i / n * months))
        y = start_year + (start_month - 1 + m_idx) // 12
        m = (start_month - 1 + m_idx) % 12 + 1
        day = (i % 27) + 1
        out.append(f"{y:04d}-{m:02d}-{day:02d}T10:00:00")
    return out


def generate_clear_drift(rng, from_key, to_key, n=12, months=6, noise=0.2):
    """전반부는 주로 from_key, 후반부는 주로 to_key. 약간의 타 가치 잡음 포함."""
    ts = _timestamps(n, months)
    others = [k for k in VALUE_KEYS if k not in (from_key, to_key)]
    cards = []
    half = n // 2
    for i, t in enumerate(ts):
        dominant = from_key if i < half else to_key
        if rng.random() < noise:
            cv = rng.choice(others)
        else:
            cv = dominant
        cards.append({"canonical_value": cv, "created_at": t})
    return {"kind": "clear_drift", "from": from_key, "to": to_key,
            "cards": cards}


def generate_flat(rng, key, n=12, months=6, noise=0.1, second_key=None):
    """안정적 흐름. second_key 가 주어지면 두 가치가 양 구간에 고르게 섞임(여전히 무변화)."""
    ts = _timestamps(n, months)
    others = [k for k in VALUE_KEYS if k != key]
    cards = []
    for t in ts:
        if second_key and rng.random() < 0.5:
            cv = second_key
        elif rng.random() < noise:
            cv = rng.choice(others)
        else:
            cv = key
        cards.append({"canonical_value": cv, "created_at": t})
    return {"kind": "flat", "from": None, "to": None, "cards": cards}


def generate_noisy(rng, n=12, months=6):
    """뚜렷한 추세 없는 무작위 혼합."""
    ts = _timestamps(n, months)
    cards = [{"canonical_value": rng.choice(VALUE_KEYS), "created_at": t} for t in ts]
    return {"kind": "noisy", "from": None, "to": None, "cards": cards}


def build_dataset(seed=42, n_clear=18, n_flat=18, n_noisy=6):
    """≥30 합성 궤적. (clear-drift recall / flat·noisy false-positive 측정용)"""
    rng = random.Random(seed)
    trajectories = []

    for _ in range(n_clear):
        from_key, to_key = rng.sample(VALUE_KEYS, 2)
        n = rng.choice([10, 12, 14, 16])
        trajectories.append(generate_clear_drift(rng, from_key, to_key, n=n, months=rng.choice([4, 6])))

    for _ in range(n_flat):
        key = rng.choice(VALUE_KEYS)
        # 절반은 단일 가치, 절반은 두 가치 안정 혼합
        second = rng.choice([k for k in VALUE_KEYS if k != key]) if rng.random() < 0.5 else None
        n = rng.choice([10, 12, 14, 16])
        trajectories.append(generate_flat(rng, key, n=n, months=rng.choice([4, 6]), second_key=second))

    for _ in range(n_noisy):
        trajectories.append(generate_noisy(rng, n=rng.choice([10, 12, 14])))

    return trajectories
