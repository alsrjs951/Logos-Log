# Week 9 — CI/CD 패키지 배포, Docker 검증 및 Dependabot/보안 자동화

> **이 문서는 생성형 AI(Gemini 3.5 Flash)의 도움을 받아 작성되었습니다.**

---

## 과제 개요

| 요구사항 | 구현 방법 | 완료 |
| :--- | :--- | :---: |
| **npm 패키지 & GitHub Packages 배포** | `@alsrjs951/week9-package` 정의, GitHub Packages (`npm.pkg.github.com`)에 배포 및 버전 자동 패치 업그레이드 (`npm version patch` 후 git push) | ✅ |
| **Docker 이미지 빌드 & GHCR 푸시** | Express 기반 경량 Dockerfile 작성, GHCR (`ghcr.io/alsrjs951/week9-app`) 빌드/푸시 자동화 | ✅ |
| **Docker 로컬 실행 검증** | Actions Runner 환경에서 컨테이너 구동 (`docker run`), 헬스체크 API (`/health`) 및 루트 API 응답 확인 후 정리 | ✅ |
| **Dependabot 정책 설정** | 스케줄(매주 월요일), 그룹 설정(prod/dev 의존성 그룹화) 및 자동 머지 조건 설정 | ✅ |
| **Dependabot 자동 머지 구현** | `dependabot-auto-merge.yml` 구축: SemVer 패치/마이너 혹은 개발 의존성 PR 승인 및 자동 스쿼시 머지 | ✅ |
| **보안 스캔 & 이슈/리포트 자동화** | `npm audit` 기반 취약점 검출 후 `$GITHUB_STEP_SUMMARY`에 리포트 출력, 고위험군(Critical/High) 발견 시 GitHub Issue 자동 발행 | ✅ |

---

## 프로젝트 구조

```text
week9/ (assignments/week9)
├── src/
│   └── index.js            # Express API 서버 및 npm 모듈 export 함수
├── Dockerfile              # 경량 Alpine 기반 Node.js 빌드 이미지 설정
├── .dockerignore           # 불필요한 빌드 컨텍스트 파일 무시
├── .gitignore              # Git 무시 파일 리스트
├── package.json            # npm 설정, 의존성 선언, GitHub Packages 레지스트리 명시
└── README.md               # [현재 문서] 9주차 과제 설명서

.github/
├── dependabot.yml          # Dependabot 패키지 업데이트 스케줄 및 그룹 정책
└── workflows/
    ├── week9-pipeline.yml            # CI/CD 메인 파이프라인 (보안스캔 -> 배포 -> Docker 검증)
    └── dependabot-auto-merge.yml     # Dependabot PR 승인 및 자동 머지 파이프라인
```

---

## 1. npm 패키지 및 GitHub Packages 배포 & 자동 버전업

**설정 파일:** [`assignments/week9/package.json`](file:///Users/lmg/Projects/Logos-Log/assignments/week9/package.json)
**워크플로우:** [`week9-pipeline.yml`](file:///Users/lmg/Projects/Logos-Log/.github/workflows/week9-pipeline.yml) (Job: `publish-package`)

- **패키지 스코프 선언**: GitHub Packages에 발행하기 위해 사용자 이름인 `alsrjs951`을 스코프로 지정하여 `@alsrjs951/week9-package`로 패키지명을 설정했습니다.
- **배포 타겟 지정**: `publishConfig` 속성을 선언하여 GitHub npm 패키지 레지스트리로 타겟을 지정했습니다.
  ```json
  "publishConfig": {
    "registry": "https://npm.pkg.github.com"
  }
  ```
- **자동 버전 업그레이드**: 워크플로우 실행 시 `npm version patch` 명령을 통해 패치 버전(예: `1.0.0` -> `1.0.1`)을 자동으로 증가시키고 변경된 `package.json` 및 Git 태그를 저장소에 push합니다. `[skip ci]` 메시지를 포함해 커밋하여 무한 빌드 루프를 방지합니다.
- **패키지 배포**: `NODE_AUTH_TOKEN`에 `secrets.GITHUB_TOKEN`을 바인딩하여 안전하게 GitHub Packages에 배포합니다.

---

## 2. Docker 이미지 빌드/푸시 및 로컬 구동 검증

**Dockerfile:** [`assignments/week9/Dockerfile`](file:///Users/lmg/Projects/Logos-Log/assignments/week9/Dockerfile)
**워크플로우:** [`week9-pipeline.yml`](file:///Users/lmg/Projects/Logos-Log/.github/workflows/week9-pipeline.yml) (Job: `docker-build-verify`)

- **경량 Docker 이미지**: `node:20-alpine` 베이스 이미지를 기반으로 설정하고, `npm ci --only=production`을 실행하여 프로덕션 빌드 속도 및 이미지 용량을 대폭 줄였습니다.
- **GHCR 자동 빌드 & 푸시**: `docker/build-push-action@v5` 및 `docker/login-action@v3`을 이용해 `ghcr.io/alsrjs951/week9-app`에 `latest` 태그 및 `vX.Y.Z` 태그를 병렬로 달아 빌드 및 푸시합니다.
- **Runner 상의 로컬 실행 검증**:
  1. 빌드 완료된 이미지를 `docker run -d -p 3000:3000`으로 백그라운드 구동합니다.
  2. 컨테이너 내부 서비스가 준비될 때까지 `curl -s http://localhost:3000/health`를 최대 15초간 폴링(Polling) 테스트합니다.
  3. 서비스 응답이 확인되면 `/health`와 `/` 엔드포인트의 JSON 바디를 분석하여 정상 구동을 증명하고, 에러 상황 시 `docker logs`를 출력하도록 예외 처리를 구성했습니다.
  4. 검증이 끝난 컨테이너는 `docker stop` & `docker rm`을 통해 깔끔히 청소(Clean-up)합니다.

---

## 3. Dependabot 정책 & 자동 머지 (Auto-Merge)

**설정 파일:** [`.github/dependabot.yml`](file:///Users/lmg/Projects/Logos-Log/.github/dependabot.yml)
**워크플로우:** [`.github/workflows/dependabot-auto-merge.yml`](file:///Users/lmg/Projects/Logos-Log/.github/workflows/dependabot-auto-merge.yml)

- **스케줄 및 대상 설정**: `npm` 에코시스템의 `/assignments/week9` 디렉토리와 `github-actions`에 대해 매주 월요일 오전 9시(KST)에 정기 업데이트 스캔을 지시합니다.
- **알림 그룹화(Grouping)**: 다량의 PR로 인한 피로도를 막기 위해 `production-dependencies`와 `development-dependencies` 그룹을 설정하여 연관된 의존성들을 단일 PR로 묶어 처리합니다.
- **조건부 자동 머지**: `dependabot-auto-merge.yml`은 Dependabot이 생성한 PR을 자동으로 검증합니다.
  - 보안 취약점이 없고, **SemVer 패치/마이너(patch/minor) 업데이트** 혹은 **개발 의존성(devDependencies)** 업데이트 조건에 부합할 경우 `gh pr review --approve`로 자동 승인합니다.
  - 그 후, `gh pr merge --auto --squash`를 호출하여 CI 통과 시 자동으로 머지가 완료되도록 구성했습니다.

---

## 4. 보안 스캔 자동화 (npm audit & Snyk)

**워크플로우:** [`week9-pipeline.yml`](file:///Users/lmg/Projects/Logos-Log/.github/workflows/week9-pipeline.yml) (Job: `security-scan`)

- **npm audit 분석 및 Markdown 보고서**: `npm audit --json`을 파싱하여 취약점 수준(Critical, High, Moderate, Low)별 개수를 추출하고, 이를 GitHub Actions의 **Step Summary**에 Markdown 테이블 리포트로 실시간 출력합니다.
- **Snyk 스캔 지원**: Repository Secrets에 `SNYK_TOKEN`이 추가되어 있는 경우 Snyk CLI 스캔을 병행하여 세밀한 보안 감사 로그를 기록합니다.
- **이슈 자동 생성**: 스캔 결과 `Critical` 또는 `High` 위험도의 취약점이 감지되면 GitHub CLI를 호출하여 **자동으로 보안 이슈를 생성**(`gh issue create`)하고 담당자에게 알림을 보냅니다. 이미 열려 있는 동일한 이슈가 있다면 중복 이슈 생성을 방지하도록 구현되었습니다.

---

## GitHub Actions 링크 및 검증용 파일 정보

- Composite Action 및 Reusable Workflow처럼 공통 CI 리소스를 활용하면서도, 주차별 독립 빌드 구조를 유지했습니다.
- 작성된 파일들의 상세 스크립트는 위의 파일 링크들을 통해 확인 가능합니다.
