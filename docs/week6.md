제공해주신 'WEEK 6 Automation with GitHub Actions' 강의 자료의 주요 내용과 실습 과제를 마크다운 문법으로 정리해 드립니다.

## 📌 강의 개요 및 학습 목표
* **과목명:** AI Open Source Software (6주차)
* **담당 교수:** 전세진 교수
* **강의 주제:** Automation with GitHub Actions
* **학습 목표:** 
    * GitHub Actions의 핵심 구성 요소(Workflow, Job, Step, Action)와 아키텍처 이해.
    * 이벤트 트리거(Push, PR 등)와 Secrets를 활용한 보안 관리 방법 습득.
    * Node.js, Python 등의 환경에서 실제 CI(지속적 통합) 파이프라인 구축 및 YAML 작성.

---

## ⚙️ GitHub Actions 아키텍처 및 핵심 구성요소
* **Workflow:** `.github/workflows/` 디렉토리에 위치하는 YAML 파일로, 하나 이상의 Job으로 구성된 자동화 프로세스입니다.
* **Event (Trigger):** 워크플로우를 실행시키는 방아쇠 역할입니다.
    * `push`: 코드 커밋 시
    * `pull_request`: PR 생성/업데이트 시
    * `schedule`: 특정 시간(Cron)에 주기적으로 실행
    * `workflow_dispatch`: 수동 실행
* **Job:** 워크플로우 내에서 실행되는 독립적인 작업 단위로, 기본적으로 병렬로 실행됩니다.
* **Runner:** Job을 실행하는 가상 서버 환경입니다 (예: `ubuntu-latest`).
* **Step:** Job 내에서 순차적으로 실행되는 개별 명령어로, 쉘 명령을 직접 실행(`run`)하거나 외부 액션을 사용(`uses`)할 수 있습니다.
* **Action:** 복잡한 작업을 캡슐화하여 재사용 가능하게 만든 단위(Plugin 개념)입니다.
    * 필수 액션: `actions/checkout@v3` (저장소 코드를 Runner 환경으로 내려받기).

---

## 🔐 고급 설정 및 보안 (Secrets)
* **Secrets 관리:** API 키나 토큰 같은 민감한 정보는 절대 코드에 하드코딩하지 말고, GitHub 저장소의 `Settings > Secrets`에 등록하여 안전하게 관리해야 합니다.
    * **접근 문법:** `env` 환경 변수와 함께 `${{ secrets.API_KEY }}` 문법을 사용하여 워크플로우에 주입합니다.
* **Job 의존성 설정 (`needs`):** Job은 기본적으로 병렬 실행되지만, `needs: build`와 같이 설정하여 이전 Job이 성공적으로 완료된 후에만 순차적으로 실행되도록 제어할 수 있습니다.
* **조건부 실행 (`if`):** `if: github.ref == 'refs/heads/main'`과 같이 컨텍스트 변수나 상태 함수(`success()`, `failure()`)를 사용하여 조건에 따라 Job/Step의 실행 여부를 결정합니다.
* **Matrix 빌드 (`strategy`):** 여러 노드 버전(`[16, 18, 20]`)이나 OS 환경에서 동시에 테스트를 병렬로 수행하여 호환성을 검증할 수 있습니다.

---

## 🚀 [중요] 6주차 실습 과제 (Missions)

직접 CI 워크플로우를 작성하고 자동화의 기초를 다지기 위한 4가지 미션입니다.

### 📝 Mission 1: 기본 CI 구축 (Hello, CI Pipeline!)
가장 기본적인 형태의 CI 워크플로우를 작성하여 코드가 푸시될 때마다 자동으로 실행되는 파이프라인을 경험합니다.
1. **프로젝트 생성:** 간단한 Node.js 또는 Python 프로젝트 생성 (의존성 관리 환경 포함).
2. **워크플로우 파일 작성:** 루트 경로에 `.github/workflows/ci.yml` 파일을 만들고, `on: push` 이벤트 트리거 설정.
3. **자동화 단계 구성:** `actions/checkout`과 언어별 `setup` 액션을 사용하여 Lint 및 Test를 실행하는 Job 정의.
4. **실행 및 검증:** GitHub에 코드를 Push하고, Actions 탭에서 성공(녹색 체크) 확인.

### 📝 Mission 2: Matrix 빌드 (Test Across Environments)
하나의 설정으로 여러 Node.js 버전 및 운영체제에서 호환성을 검증하는 파이프라인을 구축합니다.
1. **Node 버전 매트릭스:** `node-version: [16, 18, 20]` 배열을 정의하여 여러 버전 동시 테스트 설정.
2. **OS 매트릭스 확장:** `os: [ubuntu-latest, windows-latest]`를 추가하여 크로스 플랫폼 검증.
3. **전략 구성:** Job 레벨에서 `strategy` 키워드를 사용하고, `steps`에서 `${{ matrix.node-version }}`으로 참조.
4. **결과 비교 분석:** Actions 탭에서 병렬로 실행된 조합(NxM) 작업들의 성공 여부 확인.

### 📝 Mission 3: Secrets 활용 (Secure Your Secrets)
API 키나 비밀번호를 코드로 노출하지 않고 환경 변수로 안전하게 주입하는 실습입니다.
1. **GitHub Secrets 설정:** 저장소의 `Settings > Secrets` 메뉴에서 새 Secret(`API_KEY` 등) 등록.
2. **워크플로우에서 호출:** YAML 파일 내에서 `${{ secrets.API_KEY }}` 문법 사용.
3. **환경 변수 매핑:** `env` 키워드를 사용하여 Secret 값을 환경 변수나 Step의 입력값으로 전달.
4. **보안 확인:** 실행 로그에서 해당 값이 `***`로 마스킹 처리되었는지 확인.

### 📝 Mission 4: 복합 워크플로우 (Complex Workflow)
실제 배포 환경과 유사하게 Job 간 의존성을 설정하고 조건부 배포 로직을 구현합니다.
1. **3단계 파이프라인 구성:** 워크플로우 내에 `build`, `test`, `deploy`라는 3개의 별도 Job 정의.
2. **Job 의존성 설정:** `needs` 키워드를 사용하여 빌드 → 테스트 → 배포 순으로 순차 실행되게 연결.
3. **조건부 배포 설정:** Deploy Job에 `if` 조건을 추가하여, `main` 브랜치일 때만 배포 실행되도록 제한.
4. **아티팩트 전달:** 빌드 결과물을 `upload-artifact`로 저장하고 배포 단계에서 `download-artifact`로 가져와 사용.