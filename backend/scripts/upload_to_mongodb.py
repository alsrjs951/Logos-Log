import os
import json
import time
import sys
from dotenv import load_dotenv
from pymongo import MongoClient
from tqdm import tqdm

# Load environment variables
dotenv_paths = [
    os.path.join(os.path.dirname(__file__), '../.env'),
    os.path.join(os.path.dirname(__file__), '../../.env')
]
for path in dotenv_paths:
    if os.path.exists(path):
        load_dotenv(path)

EMBEDDING_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/embeddings'))
TRACK_FILE = os.path.join(EMBEDDING_DIR, 'uploaded_to_mongodb_files.json')

def main():
    uri = os.getenv("MONGODB_URI")
    if not uri:
        print("Error: MONGODB_URI가 설정되지 않았습니다.")
        sys.exit(1)

    try:
        client = MongoClient(uri)
        db = client.get_default_database("logos_log")
        print(f"Connected successfully to MongoDB Atlas database: {db.name}")
    except Exception as e:
        print(f"MongoDB 연결 실패: {e}")
        sys.exit(1)

    # Reset option check
    if "--reset" in sys.argv:
        print("Reset flag detected. MongoDB의 documents 컬렉션을 초기화합니다...")
        db.documents.delete_many({})
        if os.path.exists(TRACK_FILE):
            os.remove(TRACK_FILE)
        print("documents 컬렉션 초기화 완료.")

    uploaded_files = []
    if os.path.exists(TRACK_FILE):
        with open(TRACK_FILE, 'r') as f:
            uploaded_files = json.load(f)

    json_files = [f for f in os.listdir(EMBEDDING_DIR) if f.endswith('_embedded.json')]
    if not json_files:
        print(f"[{EMBEDDING_DIR}] 폴더에 업로드할 임베딩 JSON 파일이 없습니다.")
        return

    # 카테고리별 상위 30개 논문 파일만 선별하는 데이터 다이어트 로직
    categories = ["positive_psych", "logotherapy", "cbt", "sdt"]
    selected_files = []
    for cat in categories:
        cat_files = [f for f in json_files if f.startswith(cat)]
        cat_files.sort()
        selected_files.extend(cat_files[:30])
        print(f"카테고리 [{cat}]: {len(cat_files)}개 중 {len(cat_files[:30])}개 핵심 논문 선별 완료.")

    print(f"\n데이터 다이어트 필터링 결과: 전체 {len(json_files)}개 중 {len(selected_files)}개 논문만 엄선하여 업로드합니다.")
    json_files = selected_files

    print(f"총 {len(json_files)}개 중, 이미 업로드된 {len(uploaded_files)}개를 제외하고 업로드를 진행합니다...")
    total_chunks_uploaded = 0

    for file in json_files:
        if file in uploaded_files:
            continue
            
        file_path = os.path.join(EMBEDDING_DIR, file)
        with open(file_path, 'r', encoding='utf-8') as f:
            chunked_data = json.load(f)
            
        # OOM 방지를 위해 너무 거대한 파일은 스킵 (300 청크 이상)
        if len(chunked_data) >= 300:
            print(f"\n[{file}] 스킵됨: 청크 수 {len(chunked_data)}개가 데이터베이스 과부하를 방지하기 위해 제외됩니다.")
            uploaded_files.append(file)
            with open(TRACK_FILE, 'w') as f:
                json.dump(uploaded_files, f)
            continue
            
        print(f"\n[{file}] 파일 업로드 중... ({len(chunked_data)} 청크)")
        
        # Batch insert into MongoDB 'documents' collection
        batch_size = 50
        for i in tqdm(range(0, len(chunked_data), batch_size)):
            batch = chunked_data[i:i + batch_size]
            insert_data = []
            for record in batch:
                insert_data.append({
                    "content": record["text"],
                    "metadata": record["metadata"],
                    "embedding": record["embedding"]
                })
                
            # Perform bulk insert
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    db.documents.insert_many(insert_data)
                    total_chunks_uploaded += len(batch)
                    time.sleep(0.1)  # DB 쿨다운 딜레이
                    break
                except Exception as e:
                    print(f"\n배치 업로드 실패 (시도 {attempt}/{max_retries}): {e}")
                    if attempt == max_retries:
                        raise e
                    time.sleep(attempt * 2)
                    
        uploaded_files.append(file)
        with open(TRACK_FILE, 'w') as f:
            json.dump(uploaded_files, f)

    print(f"\n업로드 완료! 총 {total_chunks_uploaded}개의 청크가 MongoDB에 성공적으로 저장되었습니다.")

if __name__ == "__main__":
    main()
