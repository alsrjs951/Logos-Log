# Logos-Log

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/alsrjs951/Logos-Log)](https://github.com/alsrjs951/Logos-Log/issues)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/alsrjs951/Logos-Log)](https://github.com/alsrjs951/Logos-Log/pulls)
[![DORA Metrics](https://github.com/alsrjs951/Logos-Log/actions/workflows/metrics.yml/badge.svg)](https://github.com/alsrjs951/Logos-Log/actions/workflows/metrics.yml)

> DevOps 실습 프로젝트 — 로그 수집 파이프라인과 DORA 메트릭 대시보드

---

## 개요

Logos-Log는 Fluentd, Elasticsearch, Kibana 기반의 로그 수집 파이프라인과 GitHub Actions 기반 DORA 메트릭 자동화를 실습하는 오픈소스 DevOps 학습 프로젝트입니다.

```
[App Logs]
    │
    ▼
[Fluentd]  ──────────────────────────────
    │                                    │
    ▼                                    ▼
[Elasticsearch]                    [Prometheus]
    │                                    │
    ▼                                    ▼
[Kibana]                           [Grafana]
```

---

## 주요 기능

- **로그 수집**: Fluentd 에이전트로 애플리케이션 로그 수집 및 파싱
- **로그 저장**: Elasticsearch 인덱싱 및 ILM 보존 정책
- **시각화**: Kibana 대시보드
- **DORA 메트릭**: GitHub Actions로 Lead Time, Deploy Frequency, MTTR, Change Failure Rate 자동 측정
- **스프린트 관리**: GitHub Projects 칸반 보드 운영

---

## 빠른 시작

### 사전 요구 사항

- Docker 24.0+
- Docker Compose 2.20+
- Node.js 20.0+

### 실행

```bash
git clone https://github.com/alsrjs951/Logos-Log.git
cd Logos-Log
cp .env.example .env   # 환경변수 설정
docker compose up -d
```

| 서비스 | URL |
|--------|-----|
| Kibana | http://localhost:5601 |
| Elasticsearch | http://localhost:9200 |
| Grafana | http://localhost:3000 |

자세한 내용은 **[Wiki: Getting Started](https://github.com/alsrjs951/Logos-Log/wiki/Getting-Started)** 를 참고하세요.

---

## 문서

| 문서 | 링크 |
|------|------|
| Getting Started | [Wiki](https://github.com/alsrjs951/Logos-Log/wiki/Getting-Started) |
| Development Guide | [Wiki](https://github.com/alsrjs951/Logos-Log/wiki/Development-Guide) |
| Troubleshooting | [Wiki](https://github.com/alsrjs951/Logos-Log/wiki/Troubleshooting) |
| 기여 가이드 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 행동 강령 | [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) |

---

## 프로젝트 구조

```
Logos-Log/
├── .github/
│   ├── workflows/          # GitHub Actions (DORA 메트릭, 배포)
│   └── ISSUE_TEMPLATE/     # 이슈 템플릿 (Bug / Feature)
├── dashboard/              # DORA 메트릭 정적 대시보드
├── docs/                   # 주차별 강의 자료
├── week1~week6/            # 주차별 과제 결과물
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
└── LICENSE
```

---

## 기여하기

버그 제보, 기능 제안, 문서 개선 모두 환영합니다.  
기여 전에 반드시 [CONTRIBUTING.md](CONTRIBUTING.md) 를 읽어주세요.

---

## 행동 강령

이 프로젝트는 [Contributor Covenant](CODE_OF_CONDUCT.md) 행동 강령을 따릅니다.

---

## 라이선스

이 프로젝트는 [MIT License](LICENSE) 하에 배포됩니다.  
Copyright (c) 2026 Mingeon Lee
