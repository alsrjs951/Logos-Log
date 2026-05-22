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

    json_files = [f for f in os.listdir(EMBEDDING_DIR) if f.endswith('_embedded.json')]
    if not json_files:
        print(f"[{EMBEDDING_DIR}] 폴더에 업로드할 임베딩 JSON 파일이 없습니다.")
        return

    print("Supabase DB에 벡터 데이터를 업로드합니다...")
    total_chunks_uploaded = 0

    for file in json_files:
        file_path = os.path.join(EMBEDDING_DIR, file)
        with open(file_path, 'r', encoding='utf-8') as f:
            chunked_data = json.load(f)
            
        print(f"\n[{file}] 파일 업로드 중... ({len(chunked_data)} 청크)")
        
        # Insert records into 'documents' table
        for record in tqdm(chunked_data):
            try:
                # Supabase table schema에 맞춤
                data = {
                    "content": record["text"],
                    "metadata": record["metadata"],
                    "embedding": record["embedding"]
                }
                supabase.table("documents").insert(data).execute()
                total_chunks_uploaded += 1
            except Exception as e:
                print(f"업로드 실패 (chunk_id: {record.get('chunk_id')}): {e}")

    print(f"\n업로드 완료! 총 {total_chunks_uploaded}개의 청크가 Supabase에 저장되었습니다.")

if __name__ == "__main__":
    main()
