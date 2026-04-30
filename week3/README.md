# Week 3 - 칸반 기반 GitHub Project & 스프린트 백로그 구성

> **이 문서는 생성형 AI(Claude Sonnet 4.6, Anthropic)의 도움을 받아 작성되었습니다.**

---

## 목차

1. [과제 개요](#과제-개요)
2. [GitHub Project 칸반 보드](#github-project-칸반-보드)
3. [이슈 템플릿](#이슈-템플릿)
4. [라벨 체계](#라벨-체계)
5. [마일스톤 (스프린트)](#마일스톤-스프린트)
6. [이슈 백로그](#이슈-백로그)
7. [선택과제: 메트릭 분석](#선택과제-메트릭-분석)
8. [설정 방법](#설정-방법)

---

## 과제 개요

| 항목 | 내용 |
|------|------|
| 칸반 보드 | GitHub Projects v2 (5개 컬럼) |
| 이슈 템플릿 | Bug Report, Feature Request |
| 라벨 | 14개 (type / priority / status / sprint) |
| 마일스톤 | 2개 (Sprint 1, Sprint 2) |
| 이슈 수 | 13개 |

---

## GitHub Project 칸반 보드

### 보드 구성

```
┌──────────┬──────────┬─────────────┬──────────┬──────────┐
│ Backlog  │  To Do   │ In Progress │  Review  │   Done   │
├──────────┼──────────┼─────────────┼──────────┼──────────┤
│ 신규 아이 │ 이번 스프 │ 현재 작업   │ PR/검토  │ 완료된   │
│ 템 및 미  │ 린트에서  │ 중인 이슈   │ 대기 중  │ 이슈     │
│ 검토 이슈 │ 작업할   │ (WIP 제한:  │ 이슈     │          │
│          │ 이슈     │ 3개)        │          │          │
└──────────┴──────────┴─────────────┴──────────┴──────────┘
```

### GitHub Project 생성 방법 (브라우저)

`project` 스코프 권한이 필요합니다. 아래 방법으로 직접 생성하거나 `gh auth refresh -s project` 후 CLI로 생성하세요.

**브라우저 방법:**
1. https://github.com/alsrjs951/Logos-Log 접속
2. `Projects` 탭 → `New project` 클릭
3. `Board` 템플릿 선택
4. 프로젝트 이름: `Logos-Log Sprint Board`
5. 컬럼 추가: `Backlog` / `To Do` / `In Progress` / `Review` / `Done`
6. 이슈 #1~#13 을 각 컬럼에 드래그

**CLI 방법 (권한 추가 후):**
```bash
# 권한 추가
gh auth refresh -s project

# 프로젝트 생성
gh project create --owner alsrjs951 --title "Logos-Log Sprint Board"

# 이슈 추가 (PROJECT_NUMBER는 생성된 번호로 변경)
for i in $(seq 1 13); do
  gh project item-add PROJECT_NUMBER --owner alsrjs951 --url https://github.com/alsrjs951/Logos-Log/issues/$i
done
```

---

## 이슈 템플릿

### Bug Report (`.github/ISSUE_TEMPLATE/bug_report.md`)

```markdown
---
name: Bug Report
about: 버그를 발견했을 때 사용하세요
title: "[BUG] "
labels: bug, needs-triage
---

## 버그 설명
## 재현 방법
## 예상 동작
## 실제 동작
## 환경 (OS, 브라우저, 버전)
```

### Feature Request (`.github/ISSUE_TEMPLATE/feature_request.md`)

```markdown
---
name: Feature Request
about: 새로운 기능을 제안할 때 사용하세요
title: "[FEATURE] "
labels: enhancement, needs-review
---

## 기능 요약
## 동기 및 배경
## 상세 설명
## 완료 기준 (Acceptance Criteria)
## 우선순위
```

---

## 라벨 체계

### Type 라벨 (무엇을 하는가)

| 라벨 | 색상 | 설명 |
|------|------|------|
| `type: bug` | 🔴 #d73a4a | 버그 수정 |
| `type: feature` | 🔵 #0075ca | 새로운 기능 |
| `type: docs` | 🔷 #0052cc | 문서 작업 |
| `type: refactor` | 🟡 #e4e669 | 코드 리팩토링 |
| `type: test` | 🔹 #bfd4f2 | 테스트 관련 |

### Priority 라벨 (얼마나 급한가)

| 라벨 | 색상 | 설명 |
|------|------|------|
| `priority: high` | 🔴 #b60205 | 높은 우선순위 |
| `priority: medium` | 🟠 #e99695 | 중간 우선순위 |
| `priority: low` | 🟡 #f9d0c4 | 낮은 우선순위 |

### Status 라벨 (현재 상태)

| 라벨 | 색상 | 설명 |
|------|------|------|
| `status: needs-triage` | ⚪ #ededed | 트리아지 필요 |
| `status: needs-review` | 🟡 #fbca04 | 리뷰 필요 |
| `status: in-progress` | 🟢 #0e8a16 | 진행 중 |
| `status: blocked` | 🔴 #ee0701 | 블로킹됨 |

### Sprint 라벨 (어느 스프린트)

| 라벨 | 색상 | 설명 |
|------|------|------|
| `sprint: 1` | 🟢 #c2e0c6 | 스프린트 1 |
| `sprint: 2` | 🟣 #5319e7 | 스프린트 2 |

---

## 마일스톤 (스프린트)

### Sprint 1 - 기반 구축
- **기간**: ~2026-05-14
- **목표**: 로그 수집 파이프라인 및 기본 대시보드 구축
- **이슈**: #1, #2, #3, #4, #5, #6

### Sprint 2 - 분석 및 배포
- **기간**: ~2026-05-28
- **목표**: 메트릭 분석, 알림 시스템, 프로덕션 배포
- **이슈**: #7, #8, #9, #10, #11, #12, #13

---

## 이슈 백로그

| # | 제목 | 타입 | 우선순위 | 스프린트 | 상태 |
|---|------|------|---------|---------|------|
| [#1](https://github.com/alsrjs951/Logos-Log/issues/1) | 로그 수집 에이전트 구현 | feature | high | Sprint 1 | Backlog |
| [#2](https://github.com/alsrjs951/Logos-Log/issues/2) | Elasticsearch 클러스터 설정 | feature | high | Sprint 1 | Backlog |
| [#3](https://github.com/alsrjs951/Logos-Log/issues/3) | Kibana 기본 대시보드 구성 | feature | high | Sprint 1 | Backlog |
| [#4](https://github.com/alsrjs951/Logos-Log/issues/4) | 로그 파이프라인 메모리 누수 수정 | bug | high | Sprint 1 | Backlog |
| [#5](https://github.com/alsrjs951/Logos-Log/issues/5) | Docker Compose 로컬 개발 환경 구성 | feature | medium | Sprint 1 | Backlog |
| [#6](https://github.com/alsrjs951/Logos-Log/issues/6) | 로그 수집 아키텍처 문서 작성 | docs | low | Sprint 1 | Backlog |
| [#7](https://github.com/alsrjs951/Logos-Log/issues/7) | Prometheus 메트릭 수집 연동 | feature | high | Sprint 2 | Backlog |
| [#8](https://github.com/alsrjs951/Logos-Log/issues/8) | Grafana 메트릭 대시보드 구축 | feature | high | Sprint 2 | Backlog |
| [#9](https://github.com/alsrjs951/Logos-Log/issues/9) | Slack 알림 연동 | feature | medium | Sprint 2 | Backlog |
| [#10](https://github.com/alsrjs951/Logos-Log/issues/10) | Kibana 시간대 표시 오류 수정 | bug | medium | Sprint 2 | Backlog |
| [#11](https://github.com/alsrjs951/Logos-Log/issues/11) | CI/CD 파이프라인 구축 | feature | medium | Sprint 2 | Backlog |
| [#12](https://github.com/alsrjs951/Logos-Log/issues/12) | 로그 보존 정책 및 아카이빙 구현 | feature | low | Sprint 2 | Backlog |
| [#13](https://github.com/alsrjs951/Logos-Log/issues/13) | Fluentd 설정 파일 모듈화 | refactor | low | Sprint 2 | Backlog |

---

## 선택과제: 메트릭 분석

### Cycle Time

**정의**: 이슈가 `In Progress` 상태로 전환된 시점부터 `Done`으로 완료되기까지의 시간.

```
Cycle Time = Done 전환 시각 - In Progress 전환 시각
```

**GitHub Projects에서 측정하는 방법:**
1. 각 이슈의 상태 변경 이력 확인 (GraphQL API)
2. `In Progress` 이동 시각과 `Done` 이동 시각 차이 계산

**GraphQL 쿼리 예시:**
```graphql
query {
  repository(owner: "alsrjs951", name: "Logos-Log") {
    issue(number: 1) {
      timelineItems(first: 20, itemTypes: [PROJECT_V2_ITEM_STATUS_CHANGED_EVENT]) {
        nodes {
          ... on ProjectV2ItemFieldValueEvent {
            updatedAt
            fieldValue {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
              }
            }
          }
        }
      }
    }
  }
}
```

---

### Velocity

**정의**: 스프린트당 완료된 이슈 수 (또는 스토리 포인트 합계).

| 스프린트 | 계획 이슈 수 | 완료 이슈 수 | Velocity |
|---------|------------|------------|---------|
| Sprint 1 | 6 | (측정 예정) | - |
| Sprint 2 | 7 | (측정 예정) | - |

**Velocity 계산 공식:**
```
Velocity = Σ(완료된 이슈의 스토리 포인트)
평균 Velocity = Σ(각 스프린트 Velocity) / 스프린트 수
```

---

### Burndown Chart

**정의**: 스프린트 기간 동안 남은 작업량(이슈 수)이 줄어드는 추이를 나타낸 차트.

**이상적 Burndown (Sprint 1: 2주 = 14일):**

```
이슈 수
  6 |████████
  5 |        ████
  4 |            ████
  3 |                ████
  2 |                    ████
  1 |                        ████
  0 |________________________________
    Day1  Day4  Day7  Day10 Day14
```

**실제 Burndown 추적 방법:**
```bash
# 매일 실행하여 남은 이슈 수 기록
gh issue list \
  --milestone "Sprint 1 - 기반 구축" \
  --state open \
  --json number | python3 -c "import sys,json; print(len(json.load(sys.stdin)))"
```

**Burndown Chart 생성 (Python):**
```python
import matplotlib.pyplot as plt
import datetime

# 스프린트 1 데이터 (날짜, 남은 이슈 수)
sprint_start = datetime.date(2026, 5, 1)
sprint_end = datetime.date(2026, 5, 14)
total_issues = 6

# 이상적 라인
days = (sprint_end - sprint_start).days
ideal = [total_issues - (total_issues / days * i) for i in range(days + 1)]

# 실제 데이터 (매일 수동 기록)
actual = [6, 6, 5, 5, 4, 4, 3, 3, 2, 2, 1, 1, 0, 0, 0]

plt.figure(figsize=(10, 6))
plt.plot(ideal, label='Ideal Burndown', linestyle='--', color='gray')
plt.plot(actual, label='Actual Burndown', color='blue', marker='o')
plt.title('Sprint 1 Burndown Chart')
plt.xlabel('Day')
plt.ylabel('Remaining Issues')
plt.legend()
plt.grid(True)
plt.savefig('sprint1_burndown.png')
```

---

## 설정 방법

### 전체 설정 재현

```bash
# 1. 저장소 클론
git clone https://github.com/alsrjs951/Logos-Log.git
cd Logos-Log

# 2. GitHub CLI 인증 (project 스코프 포함)
gh auth login
gh auth refresh -s project

# 3. 라벨 확인
gh label list -R alsrjs951/Logos-Log

# 4. 마일스톤 확인
gh api repos/alsrjs951/Logos-Log/milestones | jq '.[].title'

# 5. 이슈 목록 확인
gh issue list -R alsrjs951/Logos-Log

# 6. GitHub Project 생성 (권한 추가 후)
gh project create --owner alsrjs951 --title "Logos-Log Sprint Board"
```

---

## 참고 자료

- [GitHub Projects 공식 문서](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
- [GitHub CLI Projects](https://cli.github.com/manual/gh_project)
- [Agile Metrics: Cycle Time, Velocity, Burndown](https://www.atlassian.com/agile/project-management/metrics)
