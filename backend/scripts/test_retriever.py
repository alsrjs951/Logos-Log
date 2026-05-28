import os
from dotenv import load_dotenv
from supabase import create_client, Client
from langchain_huggingface import HuggingFaceEmbeddings
import torch

dotenv_paths = [
    os.path.join(os.path.dirname(__file__), '../.env'),
    os.path.join(os.path.dirname(__file__), '../../.env')
]
for path in dotenv_paths:
    if os.path.exists(path):
        load_dotenv(path)

def main():
    url = os.getenv("SUPABASE_URL")
    if url:
        url = url.split("/rest/v1")[0].strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        print("Error: Supabase 환경 변수가 설정되지 않았습니다.")
        return

    supabase: Client = create_client(url, key)
    
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Using device: {device} for local embeddings")
    embeddings_model = HuggingFaceEmbeddings(
        model_name="BAAI/bge-m3",
        model_kwargs={"device": device}
    )

    print("="*60)
    print(" Logos-Log RAG Retriever Test")
    print("="*60)
    
    while True:
        try:
            query = input("\n검색할 질문을 입력하세요 (종료하려면 'q' 입력): ")
        except EOFError:
            break
            
        if query.lower() == 'q':
            break
            
        print("\n[1] 질문을 임베딩 벡터로 변환 중...")
        query_embedding = embeddings_model.embed_query(query)
        
        print("[2] Supabase Vector DB에서 유사도 검색 중...")
        try:
            # SQL에서 생성한 RPC 함수 match_documents 호출
            response = supabase.rpc("match_documents", {
                "query_embedding": query_embedding,
                "match_threshold": 0.0, # 유사도가 이 값 이상인 것만
                "match_count": 3        # 상위 3개 추출
            }).execute()
            
            results = response.data
            
            print("\n" + "="*60)
            print(f" 검색 결과 (총 {len(results)}건)")
            print("="*60)
            
            for i, res in enumerate(results, 1):
                sim = res.get('similarity', 0)
                meta = res.get('metadata', {})
                content = res.get('content', '')[:150] + "..." # 일부만 출력
                
                print(f"\n[{i}] 유사도: {sim:.4f}")
                print(f"출처: {meta.get('author', 'Unknown')} ({meta.get('year', '')}) - {meta.get('category', '')}")
                print(f"내용: {content}")
                
        except Exception as e:
            print(f"검색 중 에러 발생: {e}")

if __name__ == "__main__":
    main()
