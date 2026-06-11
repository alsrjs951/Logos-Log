# Logos-Log 데모 플레이북

이 문서는 포트폴리오 리뷰, 수업 시연, 프로젝트 발표에서 Logos-Log를 짧고 명확하게 보여주기 위한 데모 스크립트입니다. 핵심은 RAG 흐름을 과장 없이 보여주는 것입니다. Logos-Log는 연구 발췌와 주변 문맥을 검색하고, 이를 인용 가능한 성찰 가이드로 바꿉니다.

## 한 줄 소개

Logos-Log는 사용자의 고민이나 일기 내용을 심리학 연구 발췌 및 주변 문맥과 연결해, 근거 없는 조언이 아니라 근거가 보이는 성찰 질문을 제공하는 학술 기반 저널링 도구입니다.

## 데모 사전 준비

- 백엔드와 프론트엔드가 모두 실행 중이어야 합니다.
- 백엔드 환경변수에 `MONGODB_URI`, `OPENAI_API_KEY`, `JWT_SECRET`, `ENCRYPTION_KEY`가 설정되어 있어야 합니다.
- MongoDB Atlas의 `documents` 컬렉션에 영어 논문 청크가 업로드되어 있고, `vector_index` 검색 인덱스가 있어야 합니다.
- 프로덕션 검색은 vector-only 방식입니다. `$text` 하이브리드 검색은 기본 앱 경로가 아니라 평가 실험용으로만 유지합니다.

Tailscale 데스크톱 환경에서 시연할 때는 무거운 백엔드 프로세스를 데스크톱에서 실행합니다.

```bash
cd C:\Users\LeeMinGeon\Projects\Logos-Log\backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

그다음 맥북에서는 데스크톱 백엔드를 바라보도록 프론트엔드를 실행합니다.

```bash
cd frontend
VITE_API_BASE_URL=http://100.71.35.78:8000 npm run dev -- --host 127.0.0.1 --port 5173
```

긴 스트리밍 응답을 시연할 때는 직접 Tailscale IP를 사용하는 편이 좋습니다. 서버 전송 이벤트 방식에서는 SSH 터널보다 안정적이었습니다.

## 기본 데모 흐름

1. 채팅 화면을 엽니다.
2. `성과가 없으면 제가 가치 없는 사람처럼 느껴져요.`라고 질문합니다.
3. 스트리밍 답변이 생성되는 동안 인라인 인용 배지를 보여줍니다.
4. 인용 팝오버를 열어 답변 문장이 어떤 근거와 연결되는지 보여줍니다.
5. `근거 발췌` 영역을 펼쳐 출처 카드를 보여줍니다.
6. 출처 모달을 열어 논문 제목, 저자/연도, 섹션, 페이지 범위, chunk id, 발췌 요약, 안내 문구를 설명합니다.
7. UI가 `논문 전체 요약`이 아니라 `근거 발췌`라고 표현하는 이유를 설명합니다. 이 앱은 논문 전체를 읽고 요약했다고 주장하지 않고, 검색된 발췌와 주변 문맥을 근거로 답합니다.

## 추천 데모 질문

- `성과가 없으면 제가 가치 없는 사람처럼 느껴져요.`
- `번아웃이 와서 무기력한데 어떻게 회복할 수 있을까요?`
- `사람들과 잘 어울리지 못하는 것 같아 늘 외로워요.`
- `지나간 실수를 계속 곱씹으며 잠을 못 자요.`
- `병 때문에 더 이상 예전처럼 일할 수 없게 됐어요. 제 존재가 쓸모없게 느껴집니다.`

## 발표 포인트

- 이 앱은 `BAAI/bge-m3` 임베딩과 MongoDB Atlas Vector Search를 사용합니다.
- `$text` 하이브리드/RRF 검색은 평가에서 vector-only보다 낮게 나왔기 때문에, 프로덕션 검색은 vector-only로 유지했습니다.
- 승인 기준으로 삼은 평가 실행에서 검색 지표는 목표를 통과한 적이 있습니다. Context Precision `0.813`, Context Recall `0.767`입니다.
- 다음 병목은 Faithfulness입니다. 승인 기준 평가 실행에서는 `0.828`이고, 목표는 `0.90`입니다.
- UI는 검색된 발췌와 논문 전체 요약을 구분합니다. 시스템이 실제로 읽은 범위를 과장하지 않기 위해서입니다.
- verifier, claim-checker, sentence-citation template 실험은 기능 플래그 뒤에 남겨두었습니다. 다만 전체 평가 결과를 개선하지 못했기 때문에 기본값은 off입니다.

## 정직한 한계

- Logos-Log는 치료, 의료 서비스, 위기 상담 서비스가 아닙니다.
- 답변은 검색된 발췌와 주변 청크를 근거로 하며, 모든 논문을 사람이 직접 읽고 종합한 결과는 아닙니다.
- 일부 답변 문장은 아직 일반화가 강할 수 있습니다. Faithfulness 개선이 다음 품질 목표입니다.
- 평가셋과 qrels는 더 많은 전문가 검토를 통해 계속 확장해야 합니다.

## 문제 해결

- 프론트엔드가 백엔드에 연결하지 못하면 `VITE_API_BASE_URL`과 백엔드 CORS 설정을 확인합니다.
- SSH 터널에서 원격 스트리밍이 멈추면 직접 Tailscale IP를 사용합니다.
- 첫 요청은 느릴 수 있습니다. 로컬 임베딩 모델이나 reranking 모델이 warm-up될 수 있기 때문입니다.
- 출처 카드가 보이지 않으면 채팅 SSE의 `sources` 이벤트와 auth token을 확인합니다.
- 출처 모달에 메타데이터가 부족하면 MongoDB document에 `title`, `section`, `page_start`, `page_end`, `chunk_id`, `chunk_index`가 있는지 확인합니다.

## 검증 체크리스트

녹화 데모나 최종 발표 전에는 아래 명령을 실행합니다.

```bash
python -m unittest discover -s backend/tests
cd frontend && npm run lint
cd frontend && npm run build
```

큰 RAG 평가는 Tailscale 데스크톱에서 실행합니다.

```bash
python C:\Users\LeeMinGeon\Projects\Logos-Log\backend\eval\evaluate_rag.py --case-timeout 120 --judge-timeout 120
```
