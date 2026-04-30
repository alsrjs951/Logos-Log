요청하신 "week11_trunk_based_development.pdf" 파일(실제 제공된 문서는 12주차 'Shift Left Testing with Test Automation' 내용)의 핵심 내용과 과제를 마크다운 문법으로 정리해 드립니다. 

## 📌 강의 개요
* **주제:** Shift Left Testing 및 테스트 자동화를 통한 품질 향상 전략
* **핵심 목표:** 테스트 피라미드 구조 이해, Unit/Integration/E2E 테스트 작성, GitHub Actions 기반 CI/CD 파이프라인 구축, TDD(Test-Driven Development) 실천

---

## 🏗️ Shift Left Testing 및 테스트 피라미드
**Shift Left Testing**은 테스트 활동을 개발 프로세스의 초기 단계(왼쪽)로 이동시켜 결함을 조기에 발견하는 전략입니다. 프로덕션 단계에서 버그를 수정하는 비용은 개발 단계보다 **100배** 더 비싸기 때문에 빠른 피드백 루프가 필수적입니다.

http://googleusercontent.com/image_content/332



* **Test Pyramid 권장 비율 (Google Testing Blog 기준):**
  * **Unit Test (70%):** 개별 함수나 클래스를 격리하여 검증하는 가장 빠르고 저렴한 기초 테스트입니다 (도구: Jest, Vitest).
  * **Integration Test (20%):** 서비스 컴포넌트 간 상호작용(API, DB, 외부 시스템 연동)을 검증합니다 (도구: Supertest).
  * **E2E Test (10%):** 실제 사용자와 동일한 시나리오 흐름 및 UI/UX를 검증합니다. 가장 느리고 비용이 높습니다 (도구: Playwright, Cypress).

---

## 🔬 테스트 단계별 핵심 전략 및 Best Practices
* **단위 테스트 (Unit Test):**
  * **Mocking:** `fetch` 등 제어 불가능한 외부 의존성을 가짜(Mock) 함수로 대체하여 테스트를 완벽히 격리해야 합니다.
  * **4대 원칙:** AAA 패턴(Arrange-Act-Assert) 준수, 테스트 독립성 보장, 명확한 이름 사용, 하나의 테스트에서 하나의 개념만 검증하기.
* **통합 테스트 (Integration Test):**
  * **DB 격리:** Testcontainers를 활용하여 운영 환경과 유사한 Docker 컨테이너 DB를 띄우거나 In-memory DB를 사용합니다. 트랜잭션 롤백 등으로 각 테스트 전후의 데이터를 초기화해야 합니다.
* **E2E 테스트 (End-to-End):**
  * 핵심 비즈니스 가치가 있는 사용자 여정(Happy Path 및 치명적 에러 케이스)에 집중합니다.
  * 고정 시간 대기(`sleep`)를 금지하고, 프레임워크에 내장된 자동 대기(Auto-waiting) 기능을 적극적으로 활용합니다.

---

## 🔄 TDD (Test-Driven Development) 및 자동화
* **TDD 3단계 사이클:**
  1. **RED:** 구현체가 없으므로 실패하는 테스트를 먼저 작성하여 요구사항을 명세합니다.
  2. **GREEN:** 테스트를 통과하기 위한 최소한의 코드를 작성합니다.
  3. **REFACTOR:** 테스트 보호막 아래에서 기능 변경 없이 코드 구조와 가독성을 개선합니다.
* **GitHub Actions 자동화 (CI/CD):**
  * **Matrix 전략:** OS 및 Node.js 버전을 배열로 구성하여 다중 환경 크로스 플랫폼 검증을 병렬로 수행합니다.
  * **Coverage 제어:** `package.json` 내 `coverageThreshold`를 설정하여 커버리지가 특정 기준(예: **80%**) 미달 시 파이프라인을 실패시켜 코드 품질을 강제합니다.

---

## 🚀 [중요] 실습 과제 (Assignments) 상세 내용

제출 기한은 다음 수업 전까지이며, **GitHub Repository 링크 (README.md에 실행 방법 및 리포트 포함)** 형식으로 제출해야 합니다. 평가 포인트는 커버리지 달성도, TDD 사이클 준수 여부, CI 동작 확인입니다.

### 📝 Task 01: 단위 테스트 작성
* 간단한 함수(계산기, 문자열 처리 등) 로직을 구현합니다.
* Jest 프레임워크를 사용하여 테스트 케이스를 작성합니다.
* **테스트 커버리지 80% 이상** 달성을 목표로 합니다.
* GitHub Actions와 연동하여 CI 파이프라인을 구성합니다.

### 📝 Task 02: TDD 실천 (Todo App)
* Red-Green-Refactor 개발 사이클을 반드시 준수합니다 (기능 구현 전 테스트 코드 선행 작성).
* Todo App의 주요 CRUD 기능 5개 이상을 구현 완료합니다.
* Git 커밋 메시지에 TDD 단계(`feat`/`test`/`refactor`)를 명시해야 합니다.

### 📝 Task 03: E2E 테스트 자동화
* Playwright 또는 Cypress 프로젝트를 설정합니다.
* 핵심 사용자 시나리오 **3개 이상**에 대한 테스트 코드를 작성합니다.
* GitHub Actions 워크플로우에 E2E 테스트 단계를 추가합니다.
* 테스트 실패 시 디버깅을 위한 스크린샷/비디오 아티팩트 저장 설정을 구현합니다.

### 📝 Task 04: 레거시 코드 테스트
* 테스트가 없는 기존 레거시 코드를 분석합니다.
* 안전한 리팩토링을 위해 기존 동작을 보장하는 캐릭터라이제이션(Characterization) 테스트를 추가합니다.
* 리팩토링 전후로 테스트가 모두 통과하는지 확인하고, 커버리지 개선 리포트를 작성합니다.