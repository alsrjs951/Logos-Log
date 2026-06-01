import os
import json
from dotenv import load_dotenv
from supabase import create_client, Client
from tqdm import tqdm

# Load environment variables from backend/.env or root .env
dotenv_paths = [
    os.path.join(os.path.dirname(__file__), '../.env'),
    os.path.join(os.path.dirname(__file__), '../../.env')
]
for path in dotenv_paths:
    if os.path.exists(path):
        load_dotenv(path)

EMBEDDING_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/embeddings'))

def main():
    url = os.getenv("SUPABASE_URL")
    if url:
        url = url.split("/rest/v1")[0].strip()
        
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        print("Error: SUPABASE_URL 또는 SUPABASE_SERVICE_ROLE_KEY가 설정되지 않았습니다.")
        return

    supabase: Client = create_client(url, key)

    TRACK_FILE = os.path.join(EMBEDDING_DIR, 'uploaded_files.json')
    uploaded_files = []
    if os.path.exists(TRACK_FILE):
        with open(TRACK_FILE, 'r') as f:
            uploaded_files = json.load(f)

    json_files = [f for f in os.listdir(EMBEDDING_DIR) if f.endswith('_embedded.json')]
    if not json_files:
        print(f"[{EMBEDDING_DIR}] 폴더에 업로드할 임베딩 JSON 파일이 없습니다.")
        return

    print(f"총 {len(json_files)}개 중, 이미 업로드된 {len(uploaded_files)}개를 제외하고 업로드를 진행합니다...")

    print("Supabase DB에 벡터 데이터를 업로드합니다...")
    total_chunks_uploaded = 0

    for file in json_files:
        if file in uploaded_files:
            continue
            
        file_path = os.path.join(EMBEDDING_DIR, file)
        with open(file_path, 'r', encoding='utf-8') as f:
            chunked_data = json.load(f)
            
        # Skip abnormally large files to prevent Postgres OOM crashes on Nano tier
        if len(chunked_data) >= 300:
            print(f"\n[{file}] 스킵됨: 청크 수 {len(chunked_data)}개가 너무 커서 데이터베이스 과부하를 방지하기 위해 제외합니다.")
            uploaded_files.append(file)
            with open(TRACK_FILE, 'w') as f:
                json.dump(uploaded_files, f)
            continue
            
        print(f"\n[{file}] 파일 업로드 중... ({len(chunked_data)} 청크)")
        
        # Batch insert into 'documents' table - increased to 45 for significantly faster execution
        batch_size = 45
        for i in tqdm(range(0, len(chunked_data), batch_size)):
            batch = chunked_data[i:i + batch_size]
            insert_data = []
            for record in batch:
                insert_data.append({
                    "content": record["text"],
                    "metadata": record["metadata"],
                    "embedding": record["embedding"]
                })
                
            # Retry mechanism with backoff and smaller batch size on failure
            max_retries = 3
            import time
            for attempt in range(1, max_retries + 1):
                try:
                    supabase.table("documents").insert(insert_data).execute()
                    total_chunks_uploaded += len(batch)
                    time.sleep(0.5)  # Rest database between large batches
                    break
                except Exception as e:
                    print(f"\n배치 업로드 시도 {attempt}/{max_retries} 실패 (index {i}~{i+len(batch)}): {e}")
                    if attempt == max_retries:
                        # If final attempt fails, try inserting them one by one as a last resort
                        print("마지막 수단으로 1건씩 순차 등록을 시도합니다...")
                        for record in batch:
                            try:
                                supabase.table("documents").insert({
                                    "content": record["text"],
                                    "metadata": record["metadata"],
                                    "embedding": record["embedding"]
                                }).execute()
                                total_chunks_uploaded += 1
                                time.sleep(0.5)
                            except Exception as single_e:
                                print(f"단건 등록 실패: {single_e}")
                                raise single_e
                    time.sleep(attempt * 2)
                
        uploaded_files.append(file)
        with open(TRACK_FILE, 'w') as f:
            json.dump(uploaded_files, f)

    print(f"\n업로드 완료! 총 {total_chunks_uploaded}개의 청크가 Supabase에 저장되었습니다.")

if __name__ == "__main__":
    import sys
    url = os.getenv("SUPABASE_URL")
    if url:
        url = url.split("/rest/v1")[0].strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        print("Error: SUPABASE_URL 또는 SUPABASE_SERVICE_ROLE_KEY가 설정되지 않았습니다.")
        sys.exit(1)

    supabase_client: Client = create_client(url, key)

    if "--reset" in sys.argv:
        print("Reset flag detected. DB의 documents 테이블을 비우고 업로드 진행 상황을 초기화합니다...")
        
        # Delete track file
        TRACK_FILE = os.path.join(EMBEDDING_DIR, 'uploaded_files.json')
        if os.path.exists(TRACK_FILE):
            os.remove(TRACK_FILE)
            print("uploaded_files.json 초기화 완료.")

        # Delete all documents in batches of 200 by ID
        try:
            deleted_count = 0
            while True:
                res_select = supabase_client.table("documents").select("id").limit(200).execute()
                ids = [r["id"] for r in res_select.data]
                if not ids:
                    break
                supabase_client.table("documents").delete().in_("id", ids).execute()
                deleted_count += len(ids)
                print(f"삭제 진행 중... 누적 {deleted_count}개 청크 삭제됨")
            print("Supabase documents 테이블 초기화 완료.")
        except Exception as e:
            print(f"테이블 초기화 중 에러 발생: {e}")
            sys.exit(1)
            
    main()
