# MongoDB Atlas (Vector DB) 세팅 및 연동 가이드

Logos-Log 프로젝트는 논문 데이터를 벡터 형태로 저장하고 유사도 검색(RAG)을 수행하기 위해 **MongoDB Atlas Vector Search**를 활용합니다. 앱 데이터(사용자·일기·가치카드·대화)와 논문 임베딩을 하나의 클러스터에서 관리합니다. 아래 순서에 따라 클러스터 생성부터 벡터 인덱스 설정까지 진행해 주세요.

> ℹ️ 임베딩은 로컬 모델 `BAAI/bge-m3`로 생성하며 **1024차원**입니다. 벡터 인덱스 차원을 반드시 1024로 맞춰야 합니다.

---

## 1단계: MongoDB Atlas 클러스터 생성

1. [MongoDB Atlas(https://www.mongodb.com/atlas)](https://www.mongodb.com/atlas)에 접속하여 가입 및 로그인을 진행합니다. (GitHub 계정 연동 추천)
2. **[Create]** 또는 **[Build a Database]** 를 클릭합니다.
3. 플랜을 선택합니다. 학습/MVP 용도라면 무료 **M0** 티어로 충분합니다. (Atlas Vector Search는 M0에서도 지원됩니다.)
4. Provider/Region에서 가까운 지역(예: AWS `ap-northeast-2` Seoul)을 선택하고 클러스터를 생성합니다. (프로비저닝에 1~3분 소요)

---

## 2단계: 접속 보안 및 연결 문자열 확보

1. **Database Access** → **[Add New Database User]** 로 사용자/비밀번호를 생성합니다. (읽기/쓰기 권한)
2. **Network Access** → **[Add IP Address]** 로 접속 허용 IP를 등록합니다. (로컬 개발 시 본인 IP, 필요 시 `0.0.0.0/0` — 단, 운영 환경에서는 지양)
3. 클러스터 화면에서 **[Connect]** → **[Drivers]** 를 선택하고 연결 문자열(Connection String)을 복사합니다.
   - 형태: `mongodb+srv://<user>:<password>@<cluster>.xxxx.mongodb.net/?retryWrites=true&w=majority`
4. 기본 데이터베이스 이름은 `logos_log`를 사용합니다(코드 기본값). 연결 문자열 경로에 DB명을 포함하면 명시적으로 지정할 수 있습니다.
   - 예: `mongodb+srv://<user>:<password>@<cluster>.xxxx.mongodb.net/logos_log?retryWrites=true&w=majority`
5. 프로젝트 루트(또는 `backend/`)의 `.env` 파일에 다음과 같이 추가합니다.

```env
# MongoDB Atlas Configuration
MONGODB_URI="방금 복사한 연결 문자열"
```

> 일기/대화 본문은 DB에 **AES-256-GCM으로 암호화 저장**됩니다. `.env`에 `ENCRYPTION_KEY`(32바이트 base64)를 설정하세요.
> 생성: `python -c "import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"` — 분실 시 기존 암호문 복호화가 불가하니 안전하게 보관하세요.

---

## 3단계: 컬렉션 구조

별도의 스키마 선언 없이, 백엔드 코드가 다음 컬렉션을 자동으로 사용합니다(최초 쓰기 시 생성).

| 컬렉션 | 용도 | 주요 필드 |
|--------|------|-----------|
| `documents` | 논문 임베딩 청크 (RAG) | `content`, `metadata`(author/year/category), `embedding`(1024차원) |
| `users` | 사용자 계정 | `email`, `password`(bcrypt 해시), `created_at` |
| `journals` | 일기 | `title`, `content`, `emotion`, `user_id`, `created_at` |
| `value_cards` | 아하 모먼트 가치 카드 | `keyword`, `insight`, `emotion`, `user_id`, `created_at` |
| `chat_messages` | 성찰 대화 이력 | `journal_id`, `role`, `content`, `sources`, `user_id`, `created_at` |

논문 임베딩 업로드는 `backend/scripts/upload_to_mongodb.py` 로 수행합니다(로컬에서 생성한 `data/embeddings/*.json` 청크를 `documents`에 적재).

---

## 4단계: Vector Search 인덱스 생성

`documents` 컬렉션의 `embedding` 필드에 대해 Atlas Vector Search 인덱스를 만들어야 RAG 검색(`$vectorSearch`)이 동작합니다.

1. Atlas 클러스터에서 **[Atlas Search]** → **[Create Search Index]** 로 이동합니다.
2. 인덱스 유형으로 **[Vector Search]** 를 선택합니다.
3. 데이터베이스 `logos_log`, 컬렉션 `documents`를 선택합니다.
4. **인덱스 이름은 반드시 `vector_index`** 로 지정합니다(코드가 이 이름을 참조).
5. JSON 정의에 다음을 입력합니다.

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1024,
      "similarity": "cosine"
    }
  ]
}
```

6. **[Create]** 를 눌러 인덱스를 생성합니다. (인덱싱 완료까지 데이터 양에 따라 수 분 소요)

> 백엔드의 검색 파이프라인은 `$vectorSearch`(`index: "vector_index"`, `path: "embedding"`, `numCandidates: 50`, `limit: 8`)를 사용하며, 유사도 점수 0.30 이상 후보만 채택한 뒤 LLM 재랭킹으로 상위 청크를 선별합니다.

---

## ✅ 완료 확인
여기까지 완료했다면 RAG 검색 준비가 끝났습니다. `backend/scripts/upload_to_mongodb.py` 로 임베딩 청크를 적재한 뒤, `backend/scripts/test_retriever.py` 또는 `test_count.py` 로 적재·검색이 정상 동작하는지 확인할 수 있습니다.
