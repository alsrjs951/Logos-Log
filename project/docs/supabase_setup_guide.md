# Supabase (Vector DB) 세팅 및 연동 가이드

Logos-Log 프로젝트에서 논문 데이터를 벡터 형태로 저장하고 유사도 검색(RAG)을 수행하기 위해 **Supabase**를 활용합니다. 아래 순서에 따라 계정 생성부터 데이터베이스 세팅까지 진행해 주세요.

---

## 1단계: Supabase 프로젝트 생성

1. [Supabase 공식 홈페이지(https://supabase.com)](https://supabase.com/)에 접속하여 가입 및 로그인을 진행합니다. (GitHub 계정 연동 추천)
2. 대시보드에서 **[New Project]** 버튼을 클릭합니다.
3. 소속될 Organization을 선택하고(기본값 사용 무방), 프로젝트 설정 창에서 다음을 입력합니다:
   * **Name:** `Logos-Log` (원하는 이름으로 자유롭게 지정)
   * **Database Password:** `[본인이 기억할 수 있는 안전한 비밀번호]` (생성 버튼을 눌러 자동 생성한 뒤 반드시 어딘가에 메모해 두세요!)
   * **Region:** `Seoul (ap-northeast-2)` 또는 `Tokyo` 등 가까운 지역 선택
4. **[Create new project]** 버튼을 누릅니다. (데이터베이스가 프로비저닝되는 데 약 2~3분 정도 소요됩니다.)

---

## 2단계: API 키 및 URL 확보 (환경 변수 세팅)

프로젝트 세팅이 완료되면, 백엔드 서버가 데이터베이스에 접근할 수 있도록 URL과 KEY를 가져와야 합니다.

1. Supabase 왼쪽 톱니바퀴 메뉴 **[Project Settings]** -> **[API]** 탭으로 이동합니다.
2. 화면에 보이는 **Project URL** 값을 복사합니다.
3. `Project API keys` 섹션에서 `anon` `public` 키가 아닌, **`service_role` `secret`** 키의 [Reveal] 버튼을 눌러 복사합니다. 
   *(주의: service_role 키는 데이터베이스 관리자 권한을 가지므로 절대 외부에 노출되어선 안 되며, 백엔드 서버(.env)에서만 사용해야 합니다.)*
4. 프로젝트의 `backend/.env` 파일 맨 아래에 다음과 같이 추가합니다.

```env
# Supabase Configuration
SUPABASE_URL="방금 복사한 Project URL"
SUPABASE_SERVICE_ROLE_KEY="방금 복사한 service_role secret 키"
```

---

## 3단계: `pgvector` 확장 활성화 및 테이블 생성 (SQL 실행)

Supabase는 기본적으로 PostgreSQL을 사용하며, 벡터 검색을 위해 `pgvector`라는 확장(Extension)을 켜주어야 합니다.

1. Supabase 왼쪽 메뉴 모음에서 **[SQL Editor]** 아이콘을 클릭합니다.
2. **[New query]**를 클릭하여 빈 편집창을 엽니다.
3. 아래의 SQL 코드를 전부 복사하여 편집창에 붙여넣습니다.

```sql
-- 1. pgvector 확장 활성화
create extension if not exists vector;

-- 2. 논문 청크 데이터를 담을 documents 테이블 생성
create table documents (
  id uuid primary key default gen_random_uuid(),
  content text not null,       -- 텍스트 내용
  metadata jsonb,              -- 저자, 연도, 카테고리 등
  embedding vector(1536)       -- OpenAI 임베딩 벡터 공간 (1536 차원)
);

-- 3. 유사도 검색을 가속하기 위한 인덱스 (HNSW) 생성
create index on documents using hnsw (embedding vector_cosine_ops);

-- 4. 유사도 검색용 함수(Function) 생성 (RPC 호출용)
create or replace function match_documents (
  query_embedding vector(1536),
  match_threshold float,
  match_count int
)
returns table (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
)
language sql stable
as $$
  select
    documents.id,
    documents.content,
    documents.metadata,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where 1 - (documents.embedding <=> query_embedding) > match_threshold
  order by documents.embedding <=> query_embedding
  limit match_count;
$$;
```

4. 우측 하단의 **[Run]** 버튼(단축키: Cmd/Ctrl + Enter)을 눌러 코드를 실행합니다.
5. "Success" 라는 메시지가 뜨면 Vector DB 세팅이 모두 완료된 것입니다!

---

## ✅ 완료 확인
여기까지 완료하셨다면, 백엔드 개발 환경에서 데이터를 밀어넣을(Ingest) 준비가 끝났습니다. 세팅이 완료되었다고 알려주시면, 임베딩된 JSON을 데이터베이스에 업로드하는 파이썬 스크립트를 작성하겠습니다!
