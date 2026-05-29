# Week 12 — TDD Core Features, Jest 80%+ Coverage, and Playwright E2E Testing

> **이 문서는 생성형 AI(Gemini 3.5 Flash)의 도움을 받아 작성되었습니다.**

---

## 과제 개요 및 완료 현황

| 요구사항 | 구현 방식 및 완료 내용 | 완료 여부 |
| :--- | :--- | :---: |
| **Jest 단위 테스트 수립** | 핵심 비즈니스 로직에 대해 Jest 테스트 스위트 설계. 커버리지 80% 하한 임계치(Threshold) 설정 | ✅ |
| **TDD 사이클 핵심 기능 개발** | 일기 분석 모듈 `journal_analyzer.js`에 대해 **Red-Green-Refactor** 사이클을 적용하여 5개 핵심 유틸리티 완성 | ✅ |
| **80% 이상 테스트 커버리지** | 테스트 커버리지 구문/라인/함수/가지 전 영역 **100% 달성** (커버리지 스펙 통과) | ✅ |
| **Playwright E2E 시나리오** | 홈 포털 가동 검증, 헤더 정합성 체크, 버튼 클릭 인터랙션을 검사하는 시나리오 구축 | ✅ |
| **실패 시 E2E 스크린샷 캡처** | `screenshot: 'only-on-failure'`를 적용하여 테스트 실패 시 스크린샷 아티팩트(`playwright-report/`) 자동 보존 구성 | ✅ |
| **CI 연동 및 리포트 적재** | 커밋 푸시 시 CI가 단위 테스트 및 E2E 테스트를 연속 자동 실행하고, 결과를 Step Summary 및 빌드 아티팩트로 저장 | ✅ |

---

## 1. TDD (Red-Green-Refactor) 사이클 및 5개 핵심 기능

**구현 파일:** [`journal_analyzer.js`](file:///Users/lmg/Projects/Logos-Log/assignments/week12/src/journal_analyzer.js) / [`journal_analyzer.test.js`](file:///Users/lmg/Projects/Logos-Log/assignments/week12/src/journal_analyzer.test.js)

TDD 방법론을 준수하여 5개의 핵심 기능을 엄격하게 분리 개발했습니다.

### ① `validateEntry(entry)`
- **요구사항**: 일기 객체의 필수 속성(`id`, `title`, `content`, `timestamp`) 존재 여부 및 글자 수 검증.
- **Red**: 빈 입력, 누락 필드, 글자 수 제한 미만 상황의 검증 실패 테스트 작성 (FAIL).
- **Green**: 필드 검사 루프 및 `content.length < 5` 검증으로 통과 코드 작성 (PASS).
- **Refactor**: 반환값의 포맷을 `{ valid: false, reason: '...' }` 구조로 단순화하고 입력 유효성을 모듈 내부 다른 함수에서도 재사용 가능하도록 통일.

### ② `extractKeywords(text)`
- **요구사항**: 문장에서 불용어(Stopwords)를 제거하고 출현 빈도순으로 단어 정렬.
- **Red**: 구두점 제거 및 영문 불용어(`the`, `and` 등)가 필터링되는지 검증하는 테스트 작성 (FAIL).
- **Green**: 정규식을 통한 구두점 클리닝 및 `STOPWORDS` 세트 필터링 로직 구현 (PASS).
- **Refactor**: 단어 빈도가 같을 경우 알파벳 순서대로(Tie-breaker) 정렬되도록 `.sort()` 비교문 고도화.

### ③ `analyzeSentiment(text)`
- **요구사항**: 긍정/부정 사전을 통한 텍스트의 감정 점수 계산.
- **Red**: 긍정어 누적, 부정어 감산 및 동일 수일 때 중립 판정이 나오는지 검사하는 테스트 작성 (FAIL).
- **Green**: 문맥 스플릿 후 단어 매칭에 따른 점수 연산 및 분기 처리 구현 (PASS).
- **Refactor**: 대소문자 무관 처리를 위해 텍스트 `toLowerCase()` 전처리와 구두점 예외 정제 단계를 모듈화.

### ④ `findRelatedJournals(entry, allEntries)`
- **요구사항**: 키워드 공유 개수 기반 유사 일기 검색 및 정렬.
- **Red**: 자신이 결과에 노출되지 않는지, 매칭 개수가 많은 일기 순으로 자동 정렬되는지 테스트 작성 (FAIL).
- **Green**: 소스 일기의 키워드를 Set에 담아 교집합 크기를 세어 배열로 리턴하는 로직 추가 (PASS).
- **Refactor**: 관련 검색 전에 소스 일기의 정합성(`validateEntry`)을 먼저 판단해 빈 어레이를 조기 리턴(Early Exit)하도록 정리.

### ⑤ `formatExport(entry, format)`
- **요구사항**: 일기를 JSON, Markdown, Plain Text 등 다양한 확장자 포맷으로 렌더링.
- **Red**: 비정상 포맷 요청 시 예외 발생 여부 및 각 마크업 렌더링 문자열 일치 테스트 작성 (FAIL).
- **Green**: `json`, `markdown`, `text` 형태 조건문 빌드 및 에러 쓰로우 구현 (PASS).
- **Refactor**: 대소문자 미구분(`toLowerCase()`) 및 템플릿 리터럴을 활용한 가독성 확보.

---

## 2. 단위 테스트 커버리지 (Jest 100% 달성)

**설정 파일:** [`package.json`](file:///Users/lmg/Projects/Logos-Log/assignments/week12/package.json) (`jest` 필드)

`package.json`에 `coverageThreshold` 한계점을 도입하여 빌드 시점에 테스트 커버리지가 **80% 미만**으로 하락하면 파이프라인 빌드를 자동으로 차단(Build Gate)합니다.

```json
"coverageThreshold": {
  "global": {
    "branches": 80,
    "functions": 80,
    "lines": 80,
    "statements": 80
  }
}
```
현재 작성된 `journal_analyzer.test.js`는 극단적인 엣지 케이스(null 입력, 에러 상황)를 모두 커버하여 **구문/가지/함수/라인 전 부문 100% 커버리지**를 통과합니다.

---

## 3. Playwright E2E 테스트 및 실패 시 스크린샷 보관

**설정 파일:** [`playwright.config.js`](file:///Users/lmg/Projects/Logos-Log/assignments/week12/playwright.config.js)
**E2E 테스트:** [`e2e/home.spec.js`](file:///Users/lmg/Projects/Logos-Log/assignments/week12/e2e/home.spec.js)

원격 CI 가상 머신에 다른 외부 토큰이 없어도 온전하고 빠르게 브라우저 동작 검증을 수행할 수 있도록, 독립적인 Mock 서버([server.js](file:///Users/lmg/Projects/Logos-Log/assignments/week12/e2e/server.js)) 구동 아키텍처를 도입했습니다.

- **포털 가동 검증**: E2E 시나리오가 `http://localhost:3050`에 탑재된 대시보드를 방문합니다.
- **인터랙션 검증**: DOM 요소를 탐색해 타이틀이 `Logos-Log Mock Portal`인지 대조하고, 버튼을 클릭했을 때 브라우저 렌더러가 비동기로 `"Feature Flag Active!"` 문구를 노출하는지 실제 브라우저 수준에서 클릭하여 확인합니다.
- **실패 시 스크린샷 캡처 설계**:
  - `playwright.config.js` 내에 `screenshot: 'only-on-failure'`를 바인딩하여, 검증 실패(Assertion Failure) 발생 시점의 브라우저 상태를 이미지 파일로 즉시 캡처합니다.
  - 이 스냅샷 리포트는 `.github/workflows/week12-pipeline.yml` 워크플로우 내에서 `if: failure()` 트리거에 걸려, GitHub Actions 빌드 아티팩트(`playwright-report`) 영역에 자동으로 보관됩니다.
  - 이를 통해 개발자는 디버깅 시점에 브라우저 렌더링 스크린샷을 다운로드하여 실패 원인을 매우 정밀하게 추적할 수 있습니다.
