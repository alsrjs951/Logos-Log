# Week 7 — GitHub Actions CI/CD 파이프라인

> **이 문서는 생성형 AI(Claude Sonnet 4.6, Anthropic)의 도움을 받아 작성되었습니다.**

---

## 과제 개요

| 요구사항 | 구현 방법 | 완료 |
|----------|-----------|------|
| CI 워크플로우 — Lint/Test 자동 실행 | `week7-ci.yml` — ESLint + Jest | ✅ |
| Matrix 전략 (버전/OS 조합) | Node 18.x·20.x × ubuntu·windows (4조합) | ✅ |
| Secrets로 민감정보 주입 | `APP_ENV`, `API_KEY`, `DEPLOY_TOKEN` | ✅ |
| Build → Test → Deploy 의존성 | `week7-pipeline.yml` — 3-job 체인 | ✅ |
| 아티팩트 업로드/다운로드 | `upload-artifact` / `download-artifact` v4 | ✅ |

---

## 프로젝트 구조

```
week7/
├── src/
│   ├── calculator.js        # 핵심 로직 (add/subtract/multiply/divide)
│   ├── calculator.test.js   # Jest 단위 테스트
│   └── index.js             # 엔트리 포인트
├── scripts/
│   └── build.js             # 빌드 스크립트 → dist/ 생성
├── .eslintrc.json           # ESLint 규칙
└── package.json

.github/workflows/
├── week7-ci.yml             # Lint & Test (Matrix)
└── week7-pipeline.yml       # Build → Test → Deploy
```

---

## Workflow 1 — CI Lint & Test (Matrix)

**파일:** [`.github/workflows/week7-ci.yml`](../.github/workflows/week7-ci.yml)

### 트리거

```yaml
on:
  push:
    branches: [main]
    paths: ['week7/**']
  pull_request:
    branches: [main]
    paths: ['week7/**']
```

`week7/` 경로 변경이 있을 때만 실행 — 불필요한 CI 낭비 방지.

### Matrix 전략 — 4가지 조합 동시 실행

```yaml
strategy:
  fail-fast: false
  matrix:
    node-version: ['18.x', '20.x']
    os: [ubuntu-latest, windows-latest]
```

| 조합 | Runner | Node |
|------|--------|------|
| ① | ubuntu-latest | 18.x |
| ② | ubuntu-latest | 20.x |
| ③ | windows-latest | 18.x |
| ④ | windows-latest | 20.x |

`fail-fast: false` — 한 조합이 실패해도 나머지 조합은 계속 실행.

### Secrets 주입

```yaml
- name: Run Tests
  run: npm test
  env:
    APP_ENV: ${{ secrets.APP_ENV }}
    API_KEY: ${{ secrets.API_KEY }}
```

- `secrets.*` 는 GitHub Repository Settings → Secrets and variables → Actions 에 등록
- 로그에서 자동으로 `***` 마스킹됨
- 코드나 환경변수 파일에 하드코딩하지 않아도 됨

### 실행 단계

```
Checkout → Setup Node → npm install → ESLint → Jest
```

---

## Workflow 2 — Pipeline Build → Test → Deploy

**파일:** [`.github/workflows/week7-pipeline.yml`](../.github/workflows/week7-pipeline.yml)

### Job 의존성 그래프

```
build ──→ test ──→ deploy
```

`needs:` 키워드로 순서를 강제 — 이전 Job이 성공해야 다음 Job 시작.

### Job 1: Build

```yaml
build:
  runs-on: ubuntu-latest
  steps:
    - Checkout
    - Setup Node 20.x
    - npm install
    - ESLint (빌드 게이트)
    - npm run build          # dist/ 생성
    - upload-artifact@v4     # dist/ 업로드
```

`scripts/build.js` 가 `src/` 소스를 `dist/` 로 복사하고 `build-info.json` 을 생성.

### Job 2: Test

```yaml
test:
  needs: build
  steps:
    - Checkout
    - Setup Node 20.x
    - download-artifact@v4   # build Job의 dist/ 다운로드
    - dist/ 내용 검증
    - npm install
    - npm test               # Jest (APP_ENV, API_KEY secret 주입)
```

아티팩트를 다운로드해 빌드 산출물이 정상인지 먼저 검증한 뒤 테스트 실행.

### Job 3: Deploy

```yaml
deploy:
  needs: test
  steps:
    - download-artifact@v4   # 동일 아티팩트 재사용
    - Deploy (APP_ENV, DEPLOY_TOKEN secret 주입)
```

테스트가 통과한 아티팩트만 배포 단계로 진입. `DEPLOY_TOKEN` 은 실제 서버 SSH 키나 클라우드 인증 토큰으로 교체 가능.

---

## Secrets 등록 방법

1. GitHub 저장소 → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** 클릭
3. 아래 3개 등록:

| Secret 이름 | 예시 값 | 용도 |
|-------------|---------|------|
| `APP_ENV` | `production` | 실행 환경 구분 |
| `API_KEY` | `sk-xxxxxxxx` | 외부 API 인증 |
| `DEPLOY_TOKEN` | `ghp_xxxxxxxx` | 배포 인증 토큰 |

> Secrets는 등록 후 값을 다시 볼 수 없으며, 로그에서 자동으로 `***` 처리됩니다.

---

## 로컬 실행 방법

```bash
cd week7
npm install

# Lint
npm run lint

# Test
npm test

# Build
npm run build
# → dist/ 디렉터리 생성됨
```

---

## GitHub Actions 링크

| 항목 | URL |
|------|-----|
| CI 워크플로우 yml | [week7-ci.yml](https://github.com/alsrjs951/Logos-Log/blob/main/.github/workflows/week7-ci.yml) |
| Pipeline 워크플로우 yml | [week7-pipeline.yml](https://github.com/alsrjs951/Logos-Log/blob/main/.github/workflows/week7-pipeline.yml) |
| Actions 실행 내역 | [GitHub Actions](https://github.com/alsrjs951/Logos-Log/actions) |

---

## 핵심 개념 정리

### Matrix Strategy
하나의 Job 정의로 여러 환경을 병렬 실행. `matrix` 객체의 각 키/값 조합이 독립적인 Job으로 생성됨. 크로스 플랫폼 호환성과 다중 런타임 버전 지원을 검증하는 데 사용.

### Secrets
민감정보(토큰, 비밀번호, API 키)를 저장소 코드 밖에 안전하게 보관하는 GitHub 기능. 워크플로우에서 `${{ secrets.NAME }}` 으로 참조하며, Runner 메모리에만 적재되고 로그에서 자동 마스킹됨.

### Artifact 업로드/다운로드
Job 간에 파일을 전달하는 메커니즘. `upload-artifact` 로 파일을 GitHub 임시 스토리지에 저장하고, `download-artifact` 로 다른 Job에서 내려받음. 빌드 산출물을 여러 Job이 공유할 때 사용.

### Job 의존성 (`needs`)
`needs: [job-id]` 로 실행 순서를 선언. 선행 Job이 `success` 상태여야 현재 Job이 시작됨. 이를 통해 Lint 실패 시 배포가 차단되는 안전 게이트를 구성.
