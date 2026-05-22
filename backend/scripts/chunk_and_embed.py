import os
import json
from dotenv import load_dotenv
from tqdm import tqdm

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

# Load environment variables (API Key)
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

PROCESSED_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/processed'))
EMBEDDING_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/embeddings'))

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-openai-api-key-here":
        print("Error: OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        return

    if not os.path.exists(EMBEDDING_DIR):
        os.makedirs(EMBEDDING_DIR)

    json_files = [f for f in os.listdir(PROCESSED_DIR) if f.endswith('.json')]
    if not json_files:
        print(f"[{PROCESSED_DIR}] 폴더에 처리할 JSON 파일이 없습니다.")
        return

    # 1. 텍스트 청킹(Chunking) 설정
    # 문장이나 단락이 잘리지 않도록 줄바꿈과 마침표 기준으로 자름
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    # 2. 임베딩 모델 설정
    embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")

    print(f"총 {len(json_files)}개의 문서를 청킹하고 임베딩합니다...")

    for file in tqdm(json_files):
        file_path = os.path.join(PROCESSED_DIR, file)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        content = data.get("content", "")
        if not content:
            continue
            
        # 청크로 분할
        chunks = text_splitter.split_text(content)
        
        # 임베딩 생성
        embeddings = embeddings_model.embed_documents(chunks)
        
        # 결과 저장 구조 만들기
        chunked_data = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunked_data.append({
                "chunk_id": f"{data['filename']}_chunk_{i}",
                "text": chunk,
                "metadata": data.get("metadata", {}),
                "embedding": embedding
            })
            
        # 로컬 폴더에 저장
        out_filename = file.replace('.json', '_embedded.json')
        out_path = os.path.join(EMBEDDING_DIR, out_filename)
        
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(chunked_data, f, ensure_ascii=False, indent=2)
            
    print("청킹 및 임베딩 완료! 결과물이 data/embeddings/ 폴더에 임시 저장되었습니다.")

if __name__ == "__main__":
    main()
