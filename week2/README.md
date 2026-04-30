# 📊 2주차 실습 과제 진행 보고서

> ⚠️ **본 문서는 생성형 AI(Claude, GPT 등)를 활용하여 작성되었습니다.**

---

## 1. 과제 개요

| 항목 | 내용 |
|------|------|
| **과목** | AI Open Source Software (2026 Spring) |
| **주차** | 2주차 — Metrics That Matter |
| **교수** | 전세진 교수 |
| **작업 기간** | 2026.04.30 |
| **과제 수** | 3개 (DORA Metrics 자동화, 대시보드 구축, 개선 계획) |

---

## 2. 과제 1: DORA Metrics 수집 자동화

### 2.1 개요

GitHub Actions 워크플로우를 통해 DORA 4대 지표(Lead Time for Changes, Deployment Frequency, MTTR, Change Failure Rate)를 **자동으로 수집·계산·리포팅**하는 파이프라인을 구축했습니다.

### 2.2 구현 파일

| 파일 | 설명 |
|------|------|
| `.github/workflows/metrics.yml` | DORA Metrics 수집 및 주간 요약 자동화 워크플로우 |

### 2.3 워크플로우 구조

```
trigger: PR (open/close/sync) + Push (main) + Deployment + Cron (매주 월요일)

  ┌─ collect-metrics Job ──────────────────────────────┐
  │  1. Checkout (full history)                         │
  │  2. Setup Node.js + @octokit/rest                   │
  │  3. calc_metrics.mjs 실행                           │
  │     ├─ Lead Time: PR created → merged 평균 시간     │
  │     ├─ Deploy Freq: 주간 배포 횟수                  │
  │     ├─ MTTR: bug/incident 이슈 해결 평균 시간       │
  │     └─ Change Fail Rate: 실패한 워크플로우 비율      │
  │  4. JSON Artifact 업로드                            │
  │  5. metrics 브랜치에 자동 커밋                       │
  └────────────────────────────────────────────────────┘
                        │
  ┌─ weekly-summary Job (schedule/dispatch 전용) ───────┐
  │  1. Artifact 다운로드                                │
  │  2. Markdown 요약 생성                               │
  │  3. GitHub Issues 자동 등록 (peter-evans action)     │
  └────────────────────────────────────────────────────┘
```

### 2.4 DORA Metrics 계산 로직

- **Lead Time for Changes**: GitHub REST API → 최근 7일간 머지된 PR들의 `(merged_at - created_at)` 평균 (시간 단위)
- **Deployment Frequency**: `GET /repos/{owner}/{repo}/deployments` → 최근 7일 배포 건수
- **Mean Time to Recovery**: `bug`, `incident` 라벨이 붙은 이슈 → `(closed_at - created_at)` 평균
- **Change Failure Rate**: `GET /repos/{owner}/{repo}/actions/runs` → `conclusion: "failure"` 비율

### 2.5 산출물

- JSON Artifact: `dora-metrics-YYYY-MM-DD.json` (90일 보관)
- 별도 `metrics` 브랜치에 히스토리 누적 저장
- 매주 월요일 오전 9시 GitHub Issue 자동 생성

---

## 3. 과제 2: 메트릭 대시보드 구축

### 3.1 개요

**Chart.js** 기반의 웹 대시보드를 구축하여, 수집된 DORA 및 Flow Metrics를 실시간 시각화 형태로 제공합니다.

### 3.2 구현 파일

| 파일 | 설명 |
|------|------|
| `dashboard/index.html` | Chart.js + GitHub-flavored Dark 테마 대시보드 |

### 3.3 대시보드 구성

```
┌────────────────────────────────────────────────┐
│  🏷️ Badges: Metrics Pipeline  │  Build  │  Cov │
├──────────┬──────────┬──────────┬───────────────┤
│ LeadTime │  Deploy  │  MTTR    │  Change Fail  │
│  4.2h    │  8회/주  │  1.5h    │   12.5%       │
│  Elite   │  Medium  │  High    │   High        │
├──────────┴──────────┴──────────┴───────────────┤
│  📈 DORA Metrics 트렌드 (7주 라인 차트)         │
│  📊 Flow Metrics (Cycle Time, WIP, Throughput)  │
│  📉 Change Failure Rate 일별 바 차트             │
└────────────────────────────────────────────────┘
```

### 3.4 사용 기술

| 기술 | 용도 |
|------|------|
| **Chart.js** | 라인 차트, 바 차트 렌더링 |
| **GitHub API** | 데이터 소스 (REST / Actions Artifacts) |
| **GitHub Actions Badge** | `metrics.yml` 빌드 상태 뱃지 |
| **CSS Grid + Flexbox** | 반응형 레이아웃 |
| **GitHub Pages** (배포 예정) | 정적 호스팅 |

### 3.5 대시보드 시안 / 접근 방법

#### 🌐 Live Demo (GitHub Pages)

> **대시보드 URL:** [https://alsrjs951.github.io/Logos-Log/dashboard/](https://alsrjs951.github.io/Logos-Log/dashboard/)

`dashboard/index.html`을 GitHub Pages로 배포하여 브라우저에서 실시간 확인할 수 있습니다.  
배포는 `.github/workflows/deploy-dashboard.yml` 워크플로우에 의해 자동화됩니다.

#### 📸 대시보드 시안 (구현 결과)

```
┌──────────────────────────────────────────────────────────────────┐
│  📊 Logos Log — DORA Metrics Dashboard                           │
│  실시간 소프트웨어 전달 성능 지표                                   │
├──────────────────────────────────────────────────────────────────┤
│  🏷️ [Metrics Collection PASSING]  🟢 Build Passing  🟢 Cov 82%   │
├────────────┬────────────┬────────────┬───────────────────────────┤
│ ⏱️ Lead    │ 🚀 Deploy  │ 🔧 MTTR    │ ❌ Change Failure Rate    │
│   Time     │  Frequency │            │                           │
│   4.2h     │   8회/주    │   1.5h     │      12.5%               │
│  Elite     │   Medium   │   High     │      High                │
├────────────┴────────────┴────────────┴───────────────────────────┤
│                                                                   │
│  📈 DORA Metrics 트렌드 (7주)              📊 Flow Metrics        │
│  ┌─────────────────────────────┐          Cycle Time:   28.5h    │
│  │  ● Lead Time   ■ Deploy    │          WIP:           5개      │
│  │  ▲ MTTR                    │          Throughput:   14개/주   │
│  │   ↘ 추세: 전반적 개선        │          Coverage:     82%     │
│  └─────────────────────────────┘                                   │
│                                                                   │
│  📉 Change Failure Rate 상세 (일별)                                │
│  ┌─────────────────────────────────────────────┐                 │
│  │  Mon  Tue  Wed  Thu  Fri  Sat  Sun          │                 │
│  │  ██   █    ██   █    ██   █    ██  ← 목표 15%│                 │
│  └─────────────────────────────────────────────┘                 │
│                                                                   │
│  Data source: GitHub API · Updated every hour                     │
└──────────────────────────────────────────────────────────────────┘
```

> 💡 **실제 화면**은 위 GitHub Pages 링크에서 GitHub-flavored Dark 테마로 확인할 수 있습니다.  
> 위 시안은 대시보드의 구조와 배치를 나타낸 것입니다. 실제 구현 화면은 Chart.js 차트, 반응형 카드 레이아웃, GitHub 뱃지가 포함됩니다.

### 3.6 뱃지

[![Metrics Collection](https://github.com/alsrjs951/Logos-Log/actions/workflows/metrics.yml/badge.svg)](https://github.com/alsrjs951/Logos-Log/actions/workflows/metrics.yml) — GitHub Actions Metrics Pipeline Status

---

## 4. 과제 3: 개선 계획 수립

### 4.1 개요

현재 프로젝트의 가상 베이스라인 데이터를 분석하여, **SMART 원칙**에 기반한 구체적인 개선 목표와 6주 로드맵을 수립했습니다.

### 4.2 구현 파일

| 파일 | 설명 |
|------|------|
| `IMPROVEMENT.md` | 지속적 개선 계획 보고서 (전문) |

### 4.3 분석 결과 요약

#### 병목 구간 분석

```
Commit(2h) → PR Review(18h ⚠️) → CI Test(4h ⚠️) → Merge(3h) → Deploy(1.5h)

주 병목: PR Review (전체 Cycle Time의 63%)
2차 병목: CI Test 병렬화 미적용
```

#### 주요 발견 사항

| 문제점 | 심각도 | 근본 원인 |
|--------|--------|-----------|
| PR Review 18시간 지연 | 🔴 High | 리뷰어 자동 할당 부재, PR 템플릿 없음 |
| WIP 5개 과다 | 🔴 High | WIP Limit 정책 부재 |
| CI 4시간 소요 | 🟡 Medium | 테스트 병렬 실행 미적용 |
| CFR 12.5% (경계선) | 🟡 Medium | 배포 전 스모크 테스트 부재 |

### 4.4 SMART 목표

| 목표 | 현재 | 목표 | 기한 |
|------|------|------|------|
| **Lead Time 단축** | 28.5h | ≤ 6h | 4주 |
| **WIP 감축** | 5개 | ≤ 3개 | 4주 |
| **CFR 안정화** | 12.5% | ≤ 5% | 6주 |

### 4.5 개선 로드맵 (6주)

| 기간 | Phase | 주요 액션 |
|------|-------|-----------|
| 1~2주 | 즉시 개선 | PR 템플릿, CODEOWNERS, WIP Limit, CI 병렬화 |
| 3~4주 | 프로세스 개선 | Feature Flag, 스모크 테스트, Trunk-Based Dev, SLA |
| 5~6주 | 자동화 고도화 | 카나리 배포, 자동 롤백, Coverage Gate, Grafana |

---

## 5. 파일 인벤토리

| 경로 | 과제 | 상태 |
|------|------|------|
| `.github/workflows/metrics.yml` | 과제 1 | ✅ 완료 |
| `dashboard/index.html` | 과제 2 | ✅ 완료 |
| `IMPROVEMENT.md` | 과제 3 | ✅ 완료 |
| `week2/README.md` | 본 문서 | ✅ 완료 |

---

## 6. 향후 계획

- [ ] GitHub Actions workflow 실제 실행 및 스크린샷 확보
- [ ] `dashboard/index.html` → GitHub Pages 배포
- [ ] Grafana 연동을 통한 실시간 대시보드 고도화
- [ ] `IMPROVEMENT.md`의 액션 플랜 2주차 항목 실행 (PR 템플릿, CODEOWNERS 설정 등)