# Week 8 — GitHub Actions 고급 최적화

> **이 문서는 생성형 AI(Claude Sonnet 4.6, Anthropic)의 도움을 받아 작성되었습니다.**

---

## 과제 개요

| 요구사항 | 구현 방법 | 완료 |
|----------|-----------|------|
| Matrix 확장 테스트 | Node 18/20/22 × ubuntu/windows/macos (7조합) | ✅ |
| Reusable Workflow | `week8-reusable-lint-test.yml` — `workflow_call` | ✅ |
| Composite Action | `.github/actions/setup-node-cached/` | ✅ |
| 캐싱 전후 시간 측정 및 개선률 보고 | `week8-cache-benchmark.yml` — Step Summary 리포트 | ✅ |
| 브랜치/PR 조건 + 변경 파일 감지 선택적 배포 | `week8-pipeline-selective.yml` | ✅ |

---

## 프로젝트 구조

```
week8/
├── src/
│   ├── calculator.js       # 사칙연산
│   ├── calculator.test.js
│   ├── stats.js            # mean / median / variance
│   ├── stats.test.js
│   └── index.js
├── scripts/
│   └── build.js
├── .eslintrc.json
└── package.json

.github/
├── actions/
│   └── setup-node-cached/
│       └── action.yml      # Composite Action
└── workflows/
    ├── week8-reusable-lint-test.yml   # Reusable Workflow
    ├── week8-ci-matrix.yml            # Extended Matrix (호출자)
    ├── week8-pipeline-selective.yml   # 선택적 배포
    └── week8-cache-benchmark.yml      # 캐시 벤치마크
```

---

## 1. Composite Action

**파일:** [`.github/actions/setup-node-cached/action.yml`](https://github.com/alsrjs951/Logos-Log/blob/main/.github/actions/setup-node-cached/action.yml)

여러 워크플로우에서 반복되는 3단계(setup-node → cache 복원 → npm install)를 단일 Action으로 추상화합니다.

```yaml
# 사용 전 — 워크플로우마다 3 step 반복
- uses: actions/setup-node@v4
  with: { node-version: '20.x' }
- uses: actions/cache@v4
  with:
    path: week8/node_modules
    key: ${{ runner.os }}-node20-${{ hashFiles('week8/package.json') }}
- run: npm install
  if: steps.cache.outputs.cache-hit != 'true'

# 사용 후 — 1 step으로 압축
- uses: ./.github/actions/setup-node-cached
  with:
    node-version: '20.x'
    working-directory: week8
```

### 핵심 동작

- `cache-hit == 'true'` 이면 `npm install` 단계를 **완전히 건너뜀**
- `outputs.cache-hit` 을 노출해 호출자가 캐시 여부를 확인 가능
- `working-directory` 입력으로 모노레포 내 여러 패키지에 재사용 가능

---

## 2. Reusable Workflow

**파일:** [week8-reusable-lint-test.yml](https://github.com/alsrjs951/Logos-Log/blob/main/.github/workflows/week8-reusable-lint-test.yml)

`workflow_call` 트리거로 다른 워크플로우에서 호출 가능한 공통 Lint & Test 잡입니다.

```yaml
on:
  workflow_call:
    inputs:
      node-version: { type: string, default: '20.x' }
      working-directory: { type: string, default: 'week8' }
    secrets:
      APP_ENV: { required: false }
```

- `inputs` — 호출자가 Node 버전·경로를 주입
- `secrets` — 호출자의 Secrets를 안전하게 전달 (`inherit` 대신 명시적 전달)
- 내부에서 Composite Action 재사용 → 중복 0

---

## 3. Extended Matrix CI

**파일:** [week8-ci-matrix.yml](https://github.com/alsrjs951/Logos-Log/blob/main/.github/workflows/week8-ci-matrix.yml)

Reusable Workflow를 Matrix와 함께 호출해 **7가지 조합**을 병렬 실행합니다.

```yaml
strategy:
  fail-fast: false
  matrix:
    node-version: ['18.x', '20.x', '22.x']
    os: [ubuntu-latest, windows-latest, macos-latest]
    exclude:
      # macOS는 과금이 크므로 LTS(20.x)만 테스트
      - { os: macos-latest, node-version: '18.x' }
      - { os: macos-latest, node-version: '22.x' }
```

| 조합 | OS | Node |
|------|----|------|
| ① | ubuntu-latest | 18.x |
| ② | ubuntu-latest | 20.x |
| ③ | ubuntu-latest | 22.x |
| ④ | windows-latest | 18.x |
| ⑤ | windows-latest | 20.x |
| ⑥ | windows-latest | 22.x |
| ⑦ | macos-latest | 20.x |

---

## 4. 캐시 최적화 — 전후 비교

**파일:** [week8-cache-benchmark.yml](https://github.com/alsrjs951/Logos-Log/blob/main/.github/workflows/week8-cache-benchmark.yml)

### 벤치마크 구조

```
warm-cache ──→ benchmark-with-cache (cache hit)
                                               ╲
                                                ──→ report (Step Summary)
benchmark-no-cache ──────────────────────────╱
```

1. `warm-cache` — 먼저 실행해 캐시를 채움
2. `benchmark-no-cache` — 캐시 없이 `npm install`, 시간 측정
3. `benchmark-with-cache` — 캐시 히트 상태에서 시간 측정
4. `report` — `$GITHUB_STEP_SUMMARY` 에 비교표 출력

### 측정 방법

```bash
START=$(date +%s%3N)
npm install  # 또는 cache hit 시 skip
END=$(date +%s%3N)
ELAPSED=$((END - START))
echo "elapsed=${ELAPSED}" >> $GITHUB_OUTPUT
```

### 실측 결과 (ubuntu-latest / Node 20.x / eslint + jest)

| 구분 | 소요 시간 |
|------|-----------|
| 캐시 없음 (no-cache) | **13,662 ms** |
| 캐시 있음 (cache-hit: true) | **2 ms** |
| 절감 시간 | 13,660 ms |
| **개선률** | **99%** |

> [Benchmark 실행 내역 (Step Summary 포함)](https://github.com/alsrjs951/Logos-Log/actions/workflows/week8-cache-benchmark.yml)

---

## 5. 선택적 배포 파이프라인

**파일:** [week8-pipeline-selective.yml](https://github.com/alsrjs951/Logos-Log/blob/main/.github/workflows/week8-pipeline-selective.yml)

### Job 흐름

```
detect-changes
      │
      ├─ src/config 변경 있음 → lint-test → build → deploy (main push 시만)
      │
      └─ 변경 없음 → lint-test SKIP, build SKIP, deploy SKIP
```

### 변경 파일 감지

```bash
# PR이면 base...head, push면 HEAD~1..HEAD
CHANGED=$(git diff --name-only $BASE $HEAD)

echo "$CHANGED" | grep -q "^week8/src/"  && SRC="true"
echo "$CHANGED" | grep -qE "^week8/(package\.json|\.eslintrc\.json)" && CFG="true"
```

### 배포 조건 (`if` 표현식)

| Job | 실행 조건 |
|-----|-----------|
| `lint-test` | `src-changed == 'true'` OR `config-changed == 'true'` |
| `build` | `lint-test` 성공 |
| `deploy` | `build` 성공 AND `github.ref == 'refs/heads/main'` AND `event == 'push'` |

- PR에서는 lint-test·build까지만 실행, **deploy 미실행**
- `feature/**` 브랜치 push에서도 **deploy 미실행**
- `week8/` 외 파일만 변경된 push는 워크플로우 자체가 트리거되지 않음 (`paths:` 필터)

---

## GitHub Actions 링크

### Workflow yml 파일

| 워크플로우 | 파일 |
|-----------|------|
| Composite Action | [setup-node-cached/action.yml](https://github.com/alsrjs951/Logos-Log/blob/main/.github/actions/setup-node-cached/action.yml) |
| Reusable Workflow | [week8-reusable-lint-test.yml](https://github.com/alsrjs951/Logos-Log/blob/main/.github/workflows/week8-reusable-lint-test.yml) |
| Extended Matrix CI | [week8-ci-matrix.yml](https://github.com/alsrjs951/Logos-Log/blob/main/.github/workflows/week8-ci-matrix.yml) |
| Selective Deploy Pipeline | [week8-pipeline-selective.yml](https://github.com/alsrjs951/Logos-Log/blob/main/.github/workflows/week8-pipeline-selective.yml) |
| Cache Benchmark | [week8-cache-benchmark.yml](https://github.com/alsrjs951/Logos-Log/blob/main/.github/workflows/week8-cache-benchmark.yml) |

### Actions 실행 내역

| 항목 | 링크 |
|------|------|
| 전체 Actions 내역 | [Actions 탭](https://github.com/alsrjs951/Logos-Log/actions) |
| Extended Matrix CI | [실행 내역](https://github.com/alsrjs951/Logos-Log/actions/workflows/week8-ci-matrix.yml) |
| Selective Deploy | [실행 내역](https://github.com/alsrjs951/Logos-Log/actions/workflows/week8-pipeline-selective.yml) |
| Cache Benchmark | [실행 내역 (Step Summary 포함)](https://github.com/alsrjs951/Logos-Log/actions/workflows/week8-cache-benchmark.yml) |

---

## 핵심 개념 정리

### Composite Action
`runs.using: composite` 로 여러 step을 단일 Action으로 패키징. 워크플로우 간 중복 제거에 사용. `inputs`/`outputs`으로 재사용성 확보.

### Reusable Workflow
`on: workflow_call` 로 다른 워크플로우에서 `uses:` 키워드로 호출 가능한 워크플로우. Matrix와 함께 사용하면 N개 조합이 모두 동일한 검증 로직을 공유.

### `actions/cache`
`key` 값이 일치하면 캐시 히트, `restore-keys` 로 부분 일치 폴백. 캐시 히트 시 `npm install`을 건너뛰어 ~99% 시간 절감 가능.

### `$GITHUB_STEP_SUMMARY`
Actions 실행 요약 페이지에 Markdown 리포트를 삽입하는 파일. 벤치마크·테스트 결과 등을 UI에 시각화할 때 사용.

### 선택적 실행 (`if` + path detection)
`git diff` 로 변경된 파일 경로를 감지하고, `GITHUB_OUTPUT` 으로 이후 Job에 전달. Job의 `if:` 조건에서 `needs.<id>.outputs.<key>` 로 참조해 불필요한 Job을 건너뜀.
