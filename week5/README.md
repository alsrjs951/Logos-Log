# Week 5 - GitHub Wiki 문서화

> **이 문서는 생성형 AI(Claude Sonnet 4.6, Anthropic)의 도움을 받아 작성되었습니다.**

---

## 목차

1. [과제 개요](#과제-개요)
2. [Wiki 문서 구성](#wiki-문서-구성)
3. [상호 링크 구조](#상호-링크-구조)
4. [각 문서 요약](#각-문서-요약)

---

## 과제 개요

| 항목 | 내용 |
|------|------|
| Wiki URL | https://github.com/alsrjs951/Logos-Log/wiki |
| 작성 문서 수 | 4개 (Home + 필수 3개) |
| 상호 링크 | 모든 문서 상단에 전체 문서 링크 포함 |

---

## Wiki 문서 구성

| 문서 | URL | 설명 |
|------|-----|------|
| [Home](https://github.com/alsrjs951/Logos-Log/wiki) | `/wiki` | 전체 문서 허브, 프로젝트 개요 |
| [Getting Started](https://github.com/alsrjs951/Logos-Log/wiki/Getting-Started) | `/wiki/Getting-Started` | 환경 설정, 첫 실행 가이드 |
| [Development Guide](https://github.com/alsrjs951/Logos-Log/wiki/Development-Guide) | `/wiki/Development-Guide` | 브랜치 전략, 커밋 규칙, PR 규칙 |
| [Troubleshooting](https://github.com/alsrjs951/Logos-Log/wiki/Troubleshooting) | `/wiki/Troubleshooting` | 자주 발생하는 문제 및 해결 방법 |

---

## 상호 링크 구조

모든 문서 상단에 아래와 같은 네비게이션 바를 삽입하여 문서 간 이동이 가능합니다.

```
> 관련 문서: Home | Getting Started | Development Guide | Troubleshooting
```

링크 흐름:

```
         ┌─────────────────────────────────────────────────┐
         │                     Home                         │
         └──────┬──────────────────┬───────────────────────┘
                │                  │                  │
                ▼                  ▼                  ▼
      Getting Started    Development Guide     Troubleshooting
           │    ▲              │    ▲               │    ▲
           └────┘              └────┘               └────┘
         (모든 문서가 서로 링크로 연결됨)
```

---

## 각 문서 요약

### Home
- 프로젝트 전체 개요 및 아키텍처 다이어그램
- 3개 핵심 문서로의 빠른 링크 테이블

### Getting Started
- 사전 요구 사항 (Git, Docker, Node.js 등 버전 명시)
- 저장소 클론 → 환경변수 설정 → 스택 실행 → 접속 확인 5단계
- 첫 로그 전송 테스트 방법

### Development Guide
- GitHub Flow 기반 브랜치 전략 및 네이밍 규칙
- Conventional Commits 커밋 메시지 형식
- PR 규칙 및 PR 템플릿
- 디렉토리 구조 설명
- GitHub Actions 워크플로우 설명
- 스프린트 운영 방식 (칸반 보드 연동)

### Troubleshooting
- Elasticsearch: `status: red`, 메모리 부족, 포트 접속 불가
- Fluentd: 로그 미전송, 메모리 누수 (이슈 #4 연동)
- Kibana: 시간대 오류 (이슈 #10 연동), 데이터 미표시
- GitHub Actions: `@octokit/rest` 모듈 오류, `::set-output` deprecated
- Docker: 서비스 종료, 볼륨 초기화
