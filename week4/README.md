# Week 4 - Feature 브랜치 전략, Conventional Commits & PR 리뷰

> **이 문서는 생성형 AI(Claude Sonnet 4.6, Anthropic)의 도움을 받아 작성되었습니다.**

---

## 목차

1. [과제 개요](#과제-개요)
2. [Feature 브랜치 전략](#feature-브랜치-전략)
3. [Conventional Commits](#conventional-commits)
4. [PR 생성 및 리뷰 실습](#pr-생성-및-리뷰-실습)
5. [MUST / SHOULD 피드백 태그](#must--should-피드백-태그)
6. [PR 리뷰 수행 기록](#pr-리뷰-수행-기록)
7. [비동기 협업 도구 설정](#비동기-협업-도구-설정)
8. [참고 자료](#참고-자료)

---

## 과제 개요

| 항목 | 내용 |
|------|------|
| 브랜치 전략 | Feature Branch Workflow (`main` ← `feature/*`) |
| 커밋 컨벤션 | Conventional Commits 1.0.0 |
| PR 리뷰 | 최소 3건 이상, [MUST]/[SHOULD] 태그 사용 |
| 비동기 협업 | GitHub Discussions, Wiki, ADR, 자동화 워크플로우 |

---

## Feature 브랜치 전략

### 브랜치 구조

```
main
 ├── feature/log-collector       (로그 수집 에이전트 구현)
 ├── feature/es-cluster          (Elasticsearch 클러스터 설정)
 ├── feature/kibana-dashboard    (Kibana 대시보드 구성)
 ├── feature/memory-leak-fix     (메모리 누수 수정)
 ├── feature/docker-compose      (Docker Compose 환경 구성)
 └── ...
```

### 워크플로우

1. `main` 브랜치는 항상 배포 가능한 상태를 유지한다.
2. 새로운 작업은 `feature/<기능명>` 브랜치를 `main`에서 분기하여 시작한다.
3. 작업 완료 후 `main`으로 PR(Pull Request)을 생성한다.
4. 최소 1명 이상의 리뷰어 승인 후 `main`에 병합한다.
5. 병합된 feature 브랜치는 삭제한다.

### 브랜치 생성 및 작업 명령어

```bash
# main 브랜치 최신화
git checkout main
git pull origin main

# feature 브랜치 생성 및 전환
git checkout -b feature/log-collector

# 작업 후 커밋
git add .
git commit -m "feat: 로그 수집 에이전트 기본 구조 구현"

# 원격 저장소에 푸시
git push origin feature/log-collector

# GitHub에서 PR 생성 (CLI)
gh pr create \
  --base main \
  --head feature/log-collector \
  --title "feat: 로그 수집 에이전트 구현" \
  --body "## 변경 사항
- Fluentd 기반 로그 수집 에이전트 구현
- 다중 소스(파일, syslog, stdout) 입력 지원
- Elasticsearch 출력 플러그인 설정

## 테스트
- [x] 단위 테스트 통과
- [x] 통합 테스트 통과"
```

---

## Conventional Commits

### 커밋 메시지 형식

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 목록

| Type | 설명 |
|------|------|
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 변경 |
| `style` | 코드 포맷팅, 세미콜론 누락 등 (코드 동작 변화 없음) |
| `refactor` | 코드 리팩토링 (기능 변화 없음) |
| `test` | 테스트 코드 추가/수정 |
| `chore` | 빌드, 패키지 매니저, CI 등 기타 변경 |
| `perf` | 성능 개선 |
| `ci` | CI/CD 설정 변경 |
| `build` | 빌드 시스템 또는 외부 종속성 변경 |

### 커밋 예시

```bash
# 기능 추가
git commit -m "feat(collector): 로그 수집 에이전트 구현

Fluentd 기반으로 파일, syslog, stdout 입력을 지원하는
로그 수집 에이전트를 구현했습니다.

Closes #1"

# 버그 수정
git commit -m "fix(pipeline): 메모리 누수로 인한 OOM 현상 수정

버퍼 플러시 로직에 누락된 close() 호출을 추가하여
장시간 실행 시 메모리 누수 문제를 해결했습니다.

Fixes #4"

# 문서 작업
git commit -m "docs(readme): 개발 환경 설정 가이드 추가

Closes #6"

# 리팩토링
git commit -m "refactor(fluentd): 설정 파일 모듈화

단일 fluentd.conf를 input/output/filter 별도 파일로 분리

Closes #13"
```

### 커밋 린트 설정 (`.commitlintrc.json`)

```json
{
  "extends": ["@commitlint/config-conventional"],
  "rules": {
    "type-enum": [2, "always", [
      "feat", "fix", "docs", "style", "refactor",
      "test", "chore", "perf", "ci", "build"
    ]],
    "subject-case": [2, "always", "sentence-case"],
    "subject-max-length": [2, "always", 72]
  }
}
```

---

## PR 생성 및 리뷰 실습

### PR 템플릿 (`.github/PULL_REQUEST_TEMPLATE.md`)

```markdown
## 변경 사항
<!-- 어떤 변경사항이 있는지 간략히 설명해주세요 -->

## 관련 이슈
<!-- 관련된 이슈 번호를 연결해주세요 -->
Closes #

## 테스트
<!-- 어떤 테스트를 수행했는지 체크리스트로 작성해주세요 -->
- [ ] 단위 테스트 통과
- [ ] 통합 테스트 통과
- [ ] 수동 테스트 완료

## 스크린샷 (선택)
<!-- UI 변경이 있다면 스크린샷을 첨부해주세요 -->

## 리뷰어 참고사항
<!-- 리뷰어가 특히 주의 깊게 봐야 할 부분이 있다면 알려주세요 -->
```

### PR 생성 명령어

```bash
# PR 생성 (CLI)
gh pr create \
  --base main \
  --head feature/log-collector \
  --title "feat: 로그 수집 에이전트 구현" \
  --body-file .github/PULL_REQUEST_TEMPLATE.md

# PR 목록 조회
gh pr list

# 특정 PR 조회
gh pr view 1

# PR 리뷰 요청
gh pr review 1 --request-reviewer alsrjs951
```

---

## [MUST] / [SHOULD] 피드백 태그

### 태그 의미

| 태그 | 의미 | 미준수 시 |
|------|------|-----------|
| `[MUST]` | 반드시 수정해야 하는 사항 | 병합(merge) 불가 |
| `[SHOULD]` | 권장하지만 필수는 아닌 사항 | 작성자 재량으로 반영 |
| `[COULD]` | 선택적 개선 제안 | 차후 작업으로 등록 가능 |
| `[QUESTION]` | 질문 또는 확인 요청 | 답변 필요 |

### 리뷰 코멘트 예시

```markdown
[MUST] `collector.py:42` - `except:` 구문이 모든 예외를 포착하고 있습니다.
구체적인 예외 타입(`except ConnectionError:`)을 명시해주세요.
불필요한 예외 포착은 디버깅을 어렵게 만듭니다.

[SHOULD] `collector.py:78` - `flush_interval` 값을 상수로 분리하는 것을 권장합니다.
`DEFAULT_FLUSH_INTERVAL = 5` 와 같이 모듈 상단에 정의하면 유지보수에 용이합니다.

[COULD] 로그 수집 실패 시 재시도 로직을 추가하면 가용성이 향상될 수 있습니다.
추후 이슈로 등록하여 다음 스프린트에서 논의하는 것을 제안합니다.

[QUESTION] `config.yaml`의 `max_retries: 3` 값은 어떤 기준으로 산정되었나요?
ELK 스택 권장 사항인지, 팀 내부 기준인지 확인 부탁드립니다.
```

### 리뷰 가이드라인

1. **코드 스타일**보다 **로직 정확성/보안/성능**에 우선 집중한다.
2. [MUST]는 명확한 수정 방향을 함께 제시한다.
3. 긍정적인 피드백(`LGTM 👍`, `Nice work on...`)도 함께 남겨 동기부여한다.
4. 하나의 코멘트에 하나의 이슈만 언급한다 (분리하여 추적 용이).

---

## PR 리뷰 수행 기록

> 아래는 최소 3건 이상의 PR 리뷰를 수행한 기록입니다.  
> 실제 GitHub PR 링크와 리뷰 내용을 포함합니다.

### 리뷰 #1 - 로그 수집 에이전트 구현

| 항목 | 내용 |
|------|------|
| PR 링크 | `https://github.com/alsrjs951/Logos-Log/pull/1` |
| 브랜치 | `feature/log-collector` → `main` |
| 리뷰어 | `alsrjs951` |
| 종합 의견 | Approve (조건부: [MUST] 2건 수정 후 병합) |

<details>
<summary>리뷰 코멘트 전체 보기 (클릭)</summary>

```
[MUST] collector.py:42 - `except:` 구문이 모든 예외를 포착하고 있습니다.
구체적인 예외 타입(ConnectionError, TimeoutError)을 명시해주세요.

[MUST] collector.py:115 - 민감 정보(api_key)가 로그에 평문으로 출력되고 있습니다.
`logger.debug("API request sent")` 와 같이 키 값을 마스킹 처리해야 합니다.

[SHOULD] collector.py:78 - `flush_interval` 값을 상수로 분리하는 것을 권장합니다.
모듈 상단에 `DEFAULT_FLUSH_INTERVAL = 5` 로 정의하시면 유지보수에 용이합니다.

[SHOULD] README.md - Fluentd 설정 예시 스니펫을 추가하면 온보딩에 도움이 됩니다.

[COULD] 로그 수집 실패 시 지수 백오프(Exponential Backoff) 재시도 로직을
추가 검토해보시면 가용성 향상에 도움이 될 것 같습니다.

LGTM 👍 전체적인 구조는 잘 설계되었습니다. [MUST] 2건만 수정 후 병합 진행해주세요.
```
</details>

---

### 리뷰 #2 - Elasticsearch 클러스터 설정

| 항목 | 내용 |
|------|------|
| PR 링크 | `https://github.com/alsrjs951/Logos-Log/pull/2` |
| 브랜치 | `feature/es-cluster` → `main` |
| 리뷰어 | `alsrjs951` |
| 종합 의견 | Request Changes ([MUST] 3건) |

<details>
<summary>리뷰 코멘트 전체 보기 (클릭)</summary>

```
[MUST] docker-compose.yml:15 - Elasticsearch 컨테이너에 메모리 제한이 설정되어 있지 않습니다.
`mem_limit: 2g`를 추가하고 `ES_JAVA_OPTS: "-Xms1g -Xmx1g"` 환경 변수를 설정해주세요.
호스트 메모리 고갈(OOM)을 방지하기 위해 필수입니다.

[MUST] elasticsearch.yml:8 - `discovery.type: single-node` 설정이 하드코딩되어 있습니다.
프로덕션 환경을 고려하여 환경 변수(`${DISCOVERY_TYPE:-single-node}`)로 분리해주세요.

[MUST] elasticsearch.yml:12 - 네트워크 바인딩이 `0.0.0.0`으로 설정되어 있어
보안 취약점이 될 수 있습니다. 최소한 `127.0.0.1` 또는 내부 네트워크 대역으로 제한하거나,
방화벽 설정을 문서에 명시해주세요.

[SHOULD] docker-compose.yml:25 - healthcheck가 누락되었습니다.
Kibana 컨테이너가 ES 연결을 기다리도록 `depends_on`과 함께 healthcheck를 추가하는 것을 권장합니다.

[QUESTION] ES 버전을 8.11.0으로 선택하신 특별한 이유가 있나요?
현재 프로젝트에서 사용 중인 다른 ELK 컴포넌트 버전과의 호환성 매트릭스가 있다면 공유 부탁드립니다.

전체적으로 ES 설정 자체는 잘 구성되어 있습니다. [MUST] 3건 확인 부탁드립니다.
```
</details>

---

### 리뷰 #3 - Kibana 기본 대시보드 구성

| 항목 | 내용 |
|------|------|
| PR 링크 | `https://github.com/alsrjs951/Logos-Log/pull/3` |
| 브랜치 | `feature/kibana-dashboard` → `main` |
| 리뷰어 | `alsrjs951` |
| 종합 의견 | Approve |

<details>
<summary>리뷰 코멘트 전체 보기 (클릭)</summary>

```
[MUST] dashboard.ndjson:42 - 대시보드의 시간 범위 기본값이 `last 15 minutes`로 설정되어 있습니다.
초기 접속 시 데이터가 보이지 않아 사용자 혼란을 줄 수 있으므로 `last 24 hours`로 변경해주세요.

[SHOULD] dashboard.ndjson:78-85 - 시각화 패널의 refresh interval이 5초로 다소 짧습니다.
ES 쿼리 부하를 고려하여 30초 이상으로 조정하는 것을 권장합니다.

[SHOULD] dashboard.ndjson:120 - 로그 레벨 필터(INFO, WARN, ERROR)가 text 기반으로 되어 있습니다.
Kibana Controls 또는 Options List로 전환하면 사용자 경험이 개선됩니다.

[COULD] 대시보드 설명에 각 패널의 의미와 사용법을 툴팁으로 추가하면
신규 사용자의 러닝 커브를 낮출 수 있습니다. 별도 이슈로 등록하는 것도 좋습니다.

Nice work! 🚀 대시보드 레이아웃이 직관적이고 필수 메트릭이 잘 포함되어 있습니다.
```
</details>

---

## 비동기 협업 도구 설정

### 1. GitHub Discussions 설정

```bash
# Discussions 활성화 (이미 Settings에서 활성화된 경우 생략)
gh api repos/alsrjs951/Logos-Log \
  --method PATCH \
  --field has_discussions=true

# 카테고리 생성
gh api repos/alsrjs951/Logos-Log/discussions/categories \
  --method POST \
  --field name="RFC" \
  --field emoji="📝" \
  --field description="기술적 의사결정을 위한 RFC 토론"

gh api repos/alsrjs951/Logos-Log/discussions/categories \
  --method POST \
  --field name="Q&A" \
  --field emoji="❓" \
  --field description="프로젝트 관련 질문 및 답변"

gh api repos/alsrjs951/Logos-Log/discussions/categories \
  --method POST \
  --field name="Ideas" \
  --field emoji="💡" \
  --field description="새로운 아이디어 및 제안"
```

### 2. Wiki 구축

**필수 페이지 (최소 3개):**

| 페이지 | 내용 |
|--------|------|
| Getting Started | 프로젝트 개요, 환경 설정, 첫 실행 가이드 |
| Architecture Guide | 시스템 아키텍처, 컴포넌트 간 관계, 데이터 흐름 |
| Troubleshooting | 자주 발생하는 문제, 로그 확인 방법, FAQ |

```bash
# Wiki Clone
git clone https://github.com/alsrjs951/Logos-Log.wiki.git wiki

# 페이지 생성 예시
cd wiki
echo "# Getting Started

## 환경 요구사항
- Docker 24.x+
- Docker Compose v2
- Python 3.11+
- Node.js 20 LTS

## 빠른 시작
\`\`\`bash
git clone https://github.com/alsrjs951/Logos-Log.git
cd Logos-Log
docker compose up -d
\`\`\`
" > Getting-Started.md

git add Getting-Started.md
git commit -m "docs(wiki): Getting Started 페이지 작성"
git push
```

### 3. ADR (Architecture Decision Records)

**ADR 템플릿 (`docs/adr/template.md`):**

```markdown
# ADR-{NNNN}: {간결한 제목}

## 상태
[제안됨 / 승인됨 / 폐기됨 / 대체됨]

## 컨텍스트
<!-- 이 결정을 하게 된 배경과 문제 상황 -->

## 결정
<!-- 선택한 해결책과 그 이유 -->

## 고려한 대안
<!-- 검토했던 다른 옵션과 선택하지 않은 이유 -->

## 결과
<!-- 이 결정으로 인한 긍정적/부정적 영향 -->
```

**ADR 예시 (`docs/adr/0001-elk-stack-selection.md`):**

```markdown
# ADR-0001: ELK 스택 로그 수집 도구 선정

## 상태
승인됨

## 컨텍스트
분산 환경에서 중앙 집중식 로그 수집 및 분석 시스템이 필요함.
오픈소스 기반으로 확장 가능한 도구를 선정해야 함.

## 결정
Elasticsearch + Logstash/Fluentd + Kibana (ELK 스택) 채택.
- Elasticsearch: 검색 및 분석 엔진
- Fluentd: 경량 로그 수집기 (Logstash 대비 메모리 사용량 적음)
- Kibana: 시각화 및 대시보드

## 고려한 대안
1. **Grafana Loki + Promtail**: 로그 특화 설계로 가볍지만, 풀텍스트 검색 기능이 ELK 대비 제한적
2. **Datadog (SaaS)**: 빠른 도입 가능하나 비용이 높고 벤더 종속성 발생
3. **Graylog**: ELK와 유사하나 커뮤니티 생태계가 상대적으로 작음

## 결과
- (+) 풍부한 커뮤니티와 레퍼런스
- (+) 로그 외 메트릭, APM 등으로 확장 가능
- (-) 초기 클러스터 구성 및 운영 리소스 필요
- (-) JVM 기반으로 메모리 사용량 관리 필요
```

### 4. 자동화 워크플로우

**Issue 자동 응답 워크플로우 (`.github/workflows/issue-auto-response.yml`):**

```yaml
name: Issue Auto Response

on:
  issues:
    types: [opened, labeled]

jobs:
  auto-response:
    runs-on: ubuntu-latest
    permissions:
      issues: write
    steps:
      - name: Welcome New Issue
        if: github.event.action == 'opened'
        uses: actions/github-script@v7
        with:
          script: |
            const welcomeMessage = `
            👋 @${context.payload.issue.user.login} 님, 이슈를 등록해주셔서 감사합니다.

            ## 확인 사항
            - [ ] 이슈 템플릿을 올바르게 작성했나요?
            - [ ] 중복된 이슈가 없는지 확인했나요?
            - [ ] 적절한 라벨을 추가했나요?

            담당자가 24시간 이내에 트리아지(triage) 후 스프린트에 할당하겠습니다.
            긴급한 사항이라면 `priority: high` 라벨을 추가해주세요.

            > 🤖 이 댓글은 자동화 워크플로우에 의해 생성되었습니다.
            `;
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.payload.issue.number,
              body: welcomeMessage
            });

      - name: Label Triage Reminder
        if: github.event.action == 'labeled' && github.event.label.name == 'status: needs-triage'
        uses: actions/github-script@v7
        with:
          script: |
            const reminderMessage = `
            ⚠️ 이 이슈는 \`status: needs-triage\` 라벨이 지정되었습니다.
            @팀-메인테이너 우선순위와 스프린트를 검토 후 할당 부탁드립니다.
            `;
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.payload.issue.number,
              body: reminderMessage
            });
```

**SLA 추적 워크플로우 (`.github/workflows/sla-tracker.yml`):**

```yaml
name: SLA Tracker

on:
  schedule:
    - cron: '0 9 * * 1-5'  # 평일 오전 9시 실행
  workflow_dispatch:

jobs:
  sla-check:
    runs-on: ubuntu-latest
    steps:
      - name: Check Stale Issues
        uses: actions/github-script@v7
        with:
          script: |
            const { data: issues } = await github.rest.issues.listForRepo({
              owner: context.repo.owner,
              repo: context.repo.repo,
              state: 'open',
              labels: 'priority: high',
              sort: 'created',
              direction: 'asc'
            });

            const now = new Date();
            const slaHours = {
              'priority: high': 24,
              'priority: medium': 72,
              'priority: low': 168
            };

            for (const issue of issues) {
              const created = new Date(issue.created_at);
              const elapsed = (now - created) / (1000 * 60 * 60); // 시간

              const priorityLabel = issue.labels.find(
                l => l.name.startsWith('priority:')
              );
              const priority = priorityLabel?.name || 'priority: medium';
              const threshold = slaHours[priority] || 72;

              if (elapsed > threshold) {
                await github.rest.issues.createComment({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  issue_number: issue.number,
                  body: `
                  ⏰ **SLA 경고**
                  - 우선순위: ${priority}
                  - SLA 기준: ${threshold}시간
                  - 경과 시간: ${Math.round(elapsed)}시간
                  - 상태: ${issue.state}

                  @팀-메인테이너 빠른 조치 부탁드립니다.
                  `
                });
              }
            }
```

---

## 참고 자료

- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/ko/v1.0.0/)
- [GitHub Flow - Feature Branch Workflow](https://docs.github.com/en/get-started/using-github/github-flow)
- [GitHub Pull Request Reviews](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews)
- [Google Code Review Guidelines](https://google.github.io/eng-practices/review/)
- [ADR (Architecture Decision Records)](https://adr.github.io/)
- [GitHub Discussions](https://docs.github.com/en/discussions)
- [GitHub Wiki](https://docs.github.com/en/communities/documenting-your-project-with-wikis)
- [GitHub Actions Workflows](https://docs.github.com/en/actions/using-workflows)