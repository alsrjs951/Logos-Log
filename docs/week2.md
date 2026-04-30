제공해주신 'WEEK 2 Plan, Track, and Visualize Your Work' 강의 자료를 바탕으로 주요 내용과 실습 과제를 마크다운 문법으로 정리해 드립니다. 

---

## 📌 강의 개요
* **과목명:** AI Open 소스 소프트웨어 (2026년 봄학기)
* **담당 교수:** 전세진 교수
* **핵심 주제:** Agile 방법론을 기반으로 GitHub 도구를 활용한 효율적인 작업 계획, 추적 및 시각화 방법 학습

---

## 1. Agile 및 Scrum 프레임워크
* **Agile 핵심 가치:** 프로세스와 도구보다 **개인과 상호작용**, 포괄적인 문서보다 **작동하는 소프트웨어**, 계약 협상보다 **고객과의 협력**, 계획을 따르기보다 **변화에 대응하기**를 중시합니다.
* **Scrum 흐름:** Product Backlog 구성을 시작으로, Sprint Planning을 거쳐 1~4주 단위의 Sprint를 진행하며, 완료 후 Sprint Review와 Retrospective(회고)를 수행합니다.
* **Sprint 기간:** 작업 수행과 회의 사이의 이상적인 균형을 제공하며 예측 가능성이 높은 **'2주 Sprint'**를 가장 권장합니다.

## 2. GitHub Issues 및 Labels 활용
* **Issue의 역할:** 버그 및 오류 수정, 새로운 기능 요청, 문서 개선, 질문 및 토론, 기술 부채 관리 등을 추적하는 기본 단위입니다.
* **효과적인 Issue 작성:** `[Bug] 로그인 시 이메일 형식 검증 실패`와 같이 태그를 분류하고 구체적인 내용을 명시해야 합니다.
* **Label 체계:**
    * **타입 (Type):** bug, enhancement, documentation 등
    * **우선순위 (Priority):** critical, high, medium, low 등
    * **상태 (Status):** new, in-progress, ready, blocked 등
    * **크기 (Size):** XS, S, M, L, XL 등 예상 소요 시간에 따른 분류
* **자동화:** `.github/labeler.yml` 파일과 GitHub Actions를 통해 파일 변경 경로에 따라 자동으로 레이블을 부착할 수 있습니다.

## 3. GitHub Projects 및 시각화 기법
* **칸반 보드 (Kanban Board):** Backlog, To Do, In Progress, Review, Done으로 구성하여 작업 흐름을 시각화합니다.
* **WIP (Work In Progress) 제한:** 컨텍스트 스위칭 최소화를 위해 'In Progress'는 최대 3개, 'Review'는 최대 2개로 동시에 진행되는 작업 수를 제한할 것을 권장합니다.
* **작업 시각화 기법:**
    * **Burndown Chart:** 남은 작업량이 이상적인 선에 맞추어 감소하고 있는지 추적합니다.
    * **Burnup Chart:** 전체 작업 범위(Total Scope)의 변경과 완료된 작업량의 누적을 시각화합니다.
    * **CFD (Cumulative Flow Diagram):** 특정 상태의 영역이 넓어지는 것을 통해 병목 현상(Bottleneck)을 파악합니다.

## 4. 효과적인 작업 분해 및 Sprint Planning
* **User Story (사용자 스토리):** 기술적 구현 방식이 아닌 `As a [사용자 역할], I want [기능], So that [혜택]`의 형태로 가치를 명확히 정의합니다.
* **INVEST 원칙:** 좋은 User Story는 Independent(독립적), Negotiable(협상 가능), Valuable(가치 있음), Estimable(추정 가능), Small(작음), Testable(테스트 가능) 해야 합니다.
* **Capacity(가용 리소스) 산정 공식:** `팀원 수 × 근무일 × 일일 가용시간 × 이용률(보통 80%)`을 통해 현실적인 스프린트 목표를 수립합니다.

---

## 🚀 [중요] 2주차 실습 과제 (Assignments)

이번 주차에 수행해야 할 4가지 핵심 프로젝트 및 활동입니다.

### 01. GitHub Projects 설정
* 개인 프로젝트용 GitHub Project (v2) 생성
* 칸반 보드 구성 (Backlog, To Do, In Progress, Review, Done)
* 커스텀 필드 추가 (Priority, Story Points, Sprint) 및 자동화 설정

### 02. Issues & Milestones
* Issue 템플릿(Bug, Feature) 작성 및 10개 이상 이슈 생성
* Label 체계 구축 (Type, Priority, Status 등)
* Milestone 2개 생성(예: MVP, v1.1) 후 관련 Issue 할당

### 03. Sprint 실행
* 2주 Sprint 계획 수립 및 Sprint Goal 설정
* Sprint Backlog 구성 및 각 작업에 Story Points 할당
* Daily 진행상황 업데이트 및 Sprint Review 문서 초안 작성

### 04. 메트릭 수집 및 분석
* 작업 완료 후 Cycle Time 측정
* Velocity 계산 및 팀 생산성 추세 분석
* Burndown Chart 생성 및 인사이트 도출 (개선점 찾기)