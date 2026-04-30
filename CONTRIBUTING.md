# Contributing to Logos-Log

먼저 기여에 관심을 가져주셔서 감사합니다! 🎉  
이 문서는 Logos-Log 프로젝트에 기여하는 방법을 안내합니다.

---

## 목차

- [행동 강령](#행동-강령)
- [기여 방법](#기여-방법)
- [개발 환경 설정](#개발-환경-설정)
- [이슈 작성 가이드](#이슈-작성-가이드)
- [Pull Request 가이드](#pull-request-가이드)
- [커밋 메시지 규칙](#커밋-메시지-규칙)
- [브랜치 전략](#브랜치-전략)
- [코드 리뷰 기준](#코드-리뷰-기준)

---

## 행동 강령

이 프로젝트는 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)를 따릅니다.  
기여하기 전에 반드시 읽어주세요.

---

## 기여 방법

다음과 같은 방식으로 기여할 수 있습니다.

- **버그 제보**: [Bug Report 템플릿](https://github.com/alsrjs951/Logos-Log/issues/new?template=bug_report.md)으로 이슈 생성
- **기능 제안**: [Feature Request 템플릿](https://github.com/alsrjs951/Logos-Log/issues/new?template=feature_request.md)으로 이슈 생성
- **문서 개선**: Wiki 또는 README 오타·누락 수정
- **코드 기여**: 버그 수정, 기능 구현, 리팩토링

---

## 개발 환경 설정

```bash
# 1. 저장소 포크 후 클론
git clone https://github.com/<your-username>/Logos-Log.git
cd Logos-Log

# 2. 원본 저장소를 upstream으로 등록
git remote add upstream https://github.com/alsrjs951/Logos-Log.git

# 3. 환경변수 설정
cp .env.example .env

# 4. 스택 실행
docker compose up -d
```

자세한 환경 구성은 [Wiki: Getting Started](https://github.com/alsrjs951/Logos-Log/wiki/Getting-Started)를 참고하세요.

---

## 이슈 작성 가이드

- 이슈를 열기 전에 **기존 이슈를 먼저 검색**하세요.
- 버그 제보 시 재현 환경(OS, 버전)과 재현 단계를 반드시 포함하세요.
- 기능 제안 시 동기·배경과 완료 기준(Acceptance Criteria)을 작성하세요.
- 라벨(`type:`, `priority:`)을 적절히 지정해주세요.

---

## Pull Request 가이드

1. **이슈를 먼저 생성**하고, PR 본문에 `Closes #이슈번호`로 연결하세요.
2. `main` 브랜치에서 새 브랜치를 생성하세요.
3. 변경 사항이 하나의 목적에 집중되도록 작게 유지하세요.
4. PR 제목은 [커밋 메시지 규칙](#커밋-메시지-규칙)과 동일한 형식으로 작성하세요.
5. CI가 모두 통과해야 머지할 수 있습니다.
6. 리뷰어를 최소 1명 지정하세요.

### PR 체크리스트

```
- [ ] 관련 이슈가 연결되어 있다 (Closes #N)
- [ ] 브랜치명이 네이밍 규칙을 따른다
- [ ] 커밋 메시지가 Conventional Commits 형식이다
- [ ] 문서(README/Wiki)를 업데이트했다 (해당하는 경우)
- [ ] CI 체크가 모두 통과했다
```

---

## 커밋 메시지 규칙

[Conventional Commits](https://www.conventionalcommits.org/) 형식을 사용합니다.

```
<type>(<scope>): <subject>
```

| type | 설명 |
|------|------|
| `feat` | 새로운 기능 |
| `fix` | 버그 수정 |
| `docs` | 문서 변경 |
| `refactor` | 리팩토링 |
| `test` | 테스트 추가/수정 |
| `chore` | 빌드, 설정 변경 |
| `ci` | CI/CD 변경 |

**예시**

```
feat(fluentd): add nginx log parsing rule
fix(ci): prevent metrics branch race condition
docs(wiki): update troubleshooting guide
```

---

## 브랜치 전략

| 유형 | 패턴 | 예시 |
|------|------|------|
| 기능 추가 | `feature/{이슈번호}-{설명}` | `feature/1-fluentd-agent` |
| 버그 수정 | `fix/{이슈번호}-{설명}` | `fix/4-memory-leak` |
| 문서 | `docs/{설명}` | `docs/update-contributing` |
| 리팩토링 | `refactor/{설명}` | `refactor/fluentd-config` |

---

## 코드 리뷰 기준

리뷰어는 다음 항목을 기준으로 검토합니다.

- **정확성**: 코드가 의도한 대로 동작하는가?
- **보안**: SQL Injection, 비밀키 노출 등 취약점이 없는가?
- **가독성**: 변수명·함수명이 명확한가?
- **최소 변경**: 과제 범위를 벗어난 불필요한 변경이 없는가?

리뷰 의견은 건설적으로 작성하며, 모든 코멘트에 회신하거나 해결(`Resolve`) 처리해주세요.

---

질문이 있으시면 [Discussions](https://github.com/alsrjs951/Logos-Log/discussions)를 이용하거나 이슈를 열어주세요.
