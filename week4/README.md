# Week 4: Feature 브랜치 전략 & Conventional Commits & PR 리뷰 실습

> **작성 도구**: ChatGPT (OpenAI) - 생성형 AI로 작성됨

## 개요

본 과제는 GitHub Flow 기반의 **Feature 브랜치 전략**으로 작업하고, **Conventional Commits**를 적용하여 PR을 생성한 후, 최소 3건 이상의 PR 리뷰에서 **[MUST]/[SHOULD]** 태그를 사용해 구조화된 피드백을 수행하는 실습을 다룹니다.

---

## 1. Feature 브랜치 전략

### 1.1 브랜치 생성 규칙

| 브랜치 유형 | 네이밍 패턴 | 예시 |
|------------|------------|------|
| Feature | `feature/<기능명>` | `feature/es-config` |
| Bugfix | `fix/<이슈번호>-<설명>` | `fix/42-memory-leak` |
| Chore | `chore/<작업명>` | `chore/update-deps` |
| Docs | `docs/<문서명>` | `docs/api-guide` |

### 1.2 워크플로우

```
main ◄── PR Merge ── feature/es-config
  ▲                     ▲
  │                     │
  └── PR Merge ──────── feature/kibana-import
                        ▲
                        │
                        └── PR Merge ── feature/week4-async-work
```

1. `main` 브랜치에서 Feature 브랜치 생성 (`git checkout -b feature/xxx`)
2. Feature 브랜치에서 작업 후 Conventional Commits 형식으로 커밋
3. GitHub에 Push 후 PR 생성 (`gh pr create`)
4. PR 리뷰 수행 후 `main`에 Merge

---

## 2. Conventional Commits

### 2.1 커밋 메시지 형식

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### 2.2 Type 종류

| Type | 설명 |
|------|------|
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 변경 |
| `style` | 코드 포매팅, 세미콜론 누락 등 (코드 로직 변경 없음) |
| `refactor` | 코드 리팩토링 |
| `test` | 테스트 추가/수정 |
| `chore` | 빌드, 패키지 매니저 등 기타 작업 |
| `ci` | CI/CD 설정 변경 |

### 2.3 이번 주차에 사용된 커밋 예시

```bash
$ git log --oneline --grep="feat\|fix\|docs\|chore\|ci"
2b0fe98 fix(ci): metrics 브랜치 non-fast-forward 충돌 해결
d5c3594 docs(week4): Feature 브랜치 전략, Conventional Commits, PR 리뷰 가이드 작성
d599b2f feat(es): Elasticsearch Docker Compose 설정 추가
71d675f feat(kibana): Kibana 대시보드 자동 임포트 스크립트 추가
```

---

## 3. PR 생성 및 리뷰 실습

### 3.1 생성된 PR 목록 (3건)

| PR 번호 | 브랜치 | 제목 | 링크 |
|--------|--------|------|------|
| #14 | `feature/week4-async-work` | docs(week4): Feature 브랜치 전략, Conventional Commits, PR 리뷰 가이드 작성 | [Link](https://github.com/alsrjs951/Logos-Log/pull/14) |
| #15 | `feature/es-config` | feat(es): Elasticsearch Docker Compose 설정 추가 | [Link](https://github.com/alsrjs951/Logos-Log/pull/15) |
| #16 | `feature/kibana-import` | feat(kibana): Kibana 대시보드 자동 임포트 스크립트 추가 | [Link](https://github.com/alsrjs951/Logos-Log/pull/16) |

### 3.2 PR 생성 CLI 명령어

```bash
# PR 생성
gh pr create \
  --base main \
  --head feature/es-config \
  --title "feat(es): Elasticsearch Docker Compose 설정 추가" \
  --body "## 변경 사항 ..."
```

---

## 4. [MUST]/[SHOULD] 구조화된 PR 리뷰 피드백

### 4.1 태그 정의

| 태그 | 의미 | 예시 |
|------|------|------|
| **[MUST]** | 반드시 수정해야 하는 사항 (보안, 기능 결함, 심각한 성능 이슈) | `[MUST] JVM 힙 메모리 제한 누락` |
| **[SHOULD]** | 권장되는 개선 사항 (코드 일관성, 가독성, 유지보수성) | `[SHOULD] 이미지 digest 사용 고려` |

### 4.2 리뷰 수행 기록 (3건 완료)

#### 리뷰 #1 - PR #15 (`feature/es-config`)

| 태그 | 피드백 내용 | 상태 |
|------|-----------|------|
| [MUST] | JVM 힙 메모리 제한(`ES_JAVA_OPTS`) 누락 | ✅ 리뷰 완료 |
| [MUST] | 컨테이너 healthcheck 누락 | ✅ 리뷰 완료 |
| [SHOULD] | 이미지 digest 사용 고려 | ✅ 리뷰 완료 |
| [SHOULD] | 환경 변수 `.env` 파일 분리 | ✅ 리뷰 완료 |

**리뷰 링크**: https://github.com/alsrjs951/Logos-Log/pull/15#issuecomment-4353044388

#### 리뷰 #2 - PR #16 (`feature/kibana-import`)

| 태그 | 피드백 내용 | 상태 |
|------|-----------|------|
| [MUST] | 인자 개수 검증 추가 (unbound variable 방지) | ✅ 리뷰 완료 |
| [MUST] | 임시 파일 경로 `mktemp`로 경쟁 조건 해결 | ✅ 리뷰 완료 |
| [SHOULD] | 인증 헤더(`KIBANA_USER`/`KIBANA_PASSWORD`) 지원 추가 | ✅ 리뷰 완료 |
| [SHOULD] | 실행 권한 주석 개선 | ✅ 리뷰 완료 |

**리뷰 링크**: https://github.com/alsrjs951/Logos-Log/pull/16#issuecomment-4353046534

#### 리뷰 #3 - PR #14 (`feature/week4-async-work`)

| 태그 | 피드백 내용 | 상태 |
|------|-----------|------|
| [MUST] | PR 생성/리뷰 실습 섹션에 shell 명령어 예시 추가 | ✅ 리뷰 완료 |
| [MUST] | 리뷰 체크리스트 템플릿 추가 | ✅ 리뷰 완료 |
| [SHOULD] | 실제 리뷰 예시 코드 블록 추가 | ✅ 리뷰 완료 |
| [SHOULD] | GitHub Discussions/Wiki 설정 가이드 보완 | ✅ 리뷰 완료 |

**리뷰 링크**: https://github.com/alsrjs951/Logos-Log/pull/14#issuecomment-4353049008

### 4.3 리뷰 체크리스트 템플릿

PR 리뷰 시 아래 체크리스트를 참고하여 **[MUST]/[SHOULD]** 태그를 적용합니다.

```markdown
## 리뷰 체크리스트
- [ ] [MUST] Conventional Commits 형식 준수 여부
- [ ] [MUST] 보안 민감 정보 노출 여부
- [ ] [MUST] 기능/버그 수정 코드 정확성
- [ ] [SHOULD] 코드 일관성 (포매팅, 네이밍 컨벤션)
- [ ] [SHOULD] 문서화/주석
- [ ] [SHOULD] 테스트 코드 포함 여부
```

---

## 5. 비동기 협업 도구 설정

### 5.1 GitHub Discussions

- **목적**: 구조화된 Q&A, 아이디어 제안, 비동기 토론
- **설정 방법**: `Repository Settings > Features > Discussions` 체크박스 활성화

### 5.2 GitHub Wiki

- **목적**: 프로젝트 문서, 온보딩 가이드, 아키텍처 결정 기록 위키
- **설정 방법**: `Repository Settings > Features > Wikis` 활성화 후 `Wiki` 탭에서 페이지 생성

### 5.3 ADR (Architecture Decision Records)

- **목적**: 아키텍처 결정 사항을 문서화하여 컨텍스트 보존
- **ADR 템플릿 예시**:

```markdown
# ADR-001: Elasticsearch를 로그 저장소로 채택

- **상태**: 수락됨
- **결정일**: 2026-04-30
- **컨텍스트**: 분산 로그 수집 시스템에서 검색 및 집계 성능이 필요함
- **결정**: Elasticsearch 8.x를 로그 저장소로 채택
- **결과**: Kibana 대시보드 연동 가능, 수평적 확장 용이
```

### 5.4 자동화 워크플로우 (CI/CD)

- **DORA Metrics 자동 수집** (`.github/workflows/metrics.yml`)
  - PR/배포/이슈 데이터를 기반으로 Lead Time, Deploy Frequency, MTTR, Change Failure Rate 자동 계산
- **Dashboard 배포** (`.github/workflows/deploy-dashboard.yml`)
  - `main` 브랜치 Push 시 `dashboard/` 디렉토리를 GitHub Pages로 자동 배포

---

## 6. 실행한 CLI 명령어 요약

```bash
# 1. Feature 브랜치 생성
git checkout -b feature/es-config
git checkout -b feature/kibana-import
git checkout -b feature/week4-async-work

# 2. Conventional Commits 적용
git commit -m "feat(es): Elasticsearch Docker Compose 설정 추가"
git commit -m "feat(kibana): Kibana 대시보드 자동 임포트 스크립트 추가"
git commit -m "docs(week4): Feature 브랜치 전략, Conventional Commits, PR 리뷰 가이드 작성"
git commit -m "fix(ci): metrics 브랜치 non-fast-forward 충돌 해결"

# 3. PR 생성
gh pr create --base main --head feature/es-config --title "feat(es): ..." --body "..."
gh pr create --base main --head feature/kibana-import --title "feat(kibana): ..." --body "..."
gh pr create --base main --head feature/week4-async-work --title "docs(week4): ..." --body "..."

# 4. PR 리뷰 (3건)
gh pr comment 15 --body "[MUST] JVM 힙 메모리 제한 누락 ..."
gh pr comment 16 --body "[MUST] 인자 개수 검증 추가 ..."
gh pr comment 14 --body "[MUST] PR 생성/리뷰 실습 섹션에 CLI 명령어 예시 추가 ..."
```

---

## 7. 느낀 점 및 배운 점

1. **Conventional Commits**를 일관되게 적용하면 `git log --oneline` 만으로도 변경 이력을 파악하기 쉬웠습니다.
2. **[MUST]/[SHOULD]** 태그는 구두 피드백보다 훨씬 명확하게 우선순위를 전달할 수 있었습니다.
3. Feature 브랜치 전략과 PR 리뷰를 조합하면, 혼자 작업할 때도 변경 사항을 객관적으로 검토하는 효과가 있었습니다.
4. CI/CD 자동화(.github/workflows)를 통해 비동기 협업의 효율성을 높일 수 있음을 체감했습니다.

---

> ⚠️ 본 문서는 2026년 4주차 과제 수행 결과를 정리한 것으로, **ChatGPT (OpenAI) 생성형 AI**의 도움을 받아 작성되었습니다.