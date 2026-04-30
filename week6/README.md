# Week 6 - OSS 기본 구조 완성

> **이 문서는 생성형 AI(Claude Sonnet 4.6, Anthropic)의 도움을 받아 작성되었습니다.**

---

## 과제 개요

오픈소스 프로젝트의 기본 구조를 갖추는 4개 파일을 저장소 루트에 작성합니다.

| 파일 | 역할 |
|------|------|
| [LICENSE](../LICENSE) | 프로젝트 사용 조건 (MIT) |
| [README.md](../README.md) | 프로젝트 소개 및 빠른 시작 |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | 기여 방법 및 개발 규칙 |
| [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) | 커뮤니티 행동 강령 |

---

## 각 파일 상세

### LICENSE — MIT License

- 저작권자: Mingeon Lee (2026)
- 상업적 이용, 수정, 배포, 서브라이선스 허용
- 보증 없음(AS IS) 조항 포함
- `week6/LICENSE` 에 있던 파일을 저장소 루트로 복사

### README.md

루트 `README.md`는 GitHub 저장소 첫 화면에 표시되는 프로젝트의 얼굴입니다.

포함 내용:
- 뱃지 (License, Issues, PR, CI 상태)
- 프로젝트 개요 및 아키텍처 다이어그램
- 주요 기능 목록
- 빠른 시작 (사전 요구 사항 / 실행 명령 / 서비스 URL)
- 문서 링크 테이블 (Wiki, CONTRIBUTING, CODE_OF_CONDUCT)
- 프로젝트 디렉토리 구조
- 기여 방법 안내
- 라이선스

### CONTRIBUTING.md

기여자가 PR을 열기 전에 읽어야 할 가이드입니다.

포함 내용:
- 기여 방법 (버그 제보 / 기능 제안 / 문서 / 코드)
- 개발 환경 설정 (fork → clone → upstream 등록 → 실행)
- 이슈 작성 가이드 (기존 이슈 검색, 라벨 지정)
- PR 가이드 및 체크리스트
- Conventional Commits 커밋 메시지 규칙
- 브랜치 네이밍 전략
- 코드 리뷰 기준

### CODE_OF_CONDUCT.md

Contributor Covenant v1.4 기반의 커뮤니티 행동 강령입니다.

포함 내용:
- 긍정적 환경을 위한 행동 기준
- 허용되지 않는 행동 목록
- 관리자의 책임과 시행 범위
- 위반 신고 방법 (이메일)

---

## OSS 구조 체크리스트

| 항목 | 파일 | 완료 |
|------|------|------|
| 오픈소스 라이선스 | `LICENSE` | ✅ |
| 프로젝트 소개 | `README.md` | ✅ |
| 기여 가이드 | `CONTRIBUTING.md` | ✅ |
| 행동 강령 | `CODE_OF_CONDUCT.md` | ✅ |
| 이슈 템플릿 | `.github/ISSUE_TEMPLATE/` | ✅ (week3) |
| PR 템플릿 | CONTRIBUTING.md 내 명시 | ✅ |
