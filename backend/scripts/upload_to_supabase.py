import os
import json
from dotenv import load_dotenv
from supabase import create_client, Client
from tqdm import tqdm

load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

EMBEDDING_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/embeddings'))

def main():
    url = os.getenv("SUPABASE_URL")
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
            
        print(f"\n[{file}] 파일 업로드 중... ({len(chunked_data)} 청크)")
        
        # Batch insert into 'documents' table
        batch_size = 500
        for i in tqdm(range(0, len(chunked_data), batch_size)):
            batch = chunked_data[i:i + batch_size]
            insert_data = []
            for record in batch:
                insert_data.append({
                    "content": record["text"],
                    "metadata": record["metadata"],
                    "embedding": record["embedding"]
                })
                
            try:
                supabase.table("documents").insert(insert_data).execute()
                total_chunks_uploaded += len(batch)
            except Exception as e:
                print(f"배치 업로드 실패 (index {i}~{i+len(batch)}): {e}")
                
        uploaded_files.append(file)
        with open(TRACK_FILE, 'w') as f:
            json.dump(uploaded_files, f)

    print(f"\n업로드 완료! 총 {total_chunks_uploaded}개의 청크가 Supabase에 저장되었습니다.")

if __name__ == "__main__":
    main()
