import os
import re
import json
import fitz  # PyMuPDF
from tqdm import tqdm

RAW_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/raw'))
PROCESSED_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/processed'))

def clean_text(text: str) -> str:
    """
    논문 텍스트에서 불필요한 노이즈(연속된 공백, 줄바꿈, 페이지 번호 등)를 제거합니다.
    """
    # 다중 공백 및 줄바꿈을 단일 공백으로 치환
    text = re.sub(r'\s+', ' ', text)
    # 논문 등에 흔히 나타나는 URL이나 불필요한 메타문자 제거
    text = re.sub(r'http[s]?://\S+', '', text)
    # 특수기호 최소화 (필요에 따라 정규식 수정)
    text = re.sub(r'[^\w\s.,!?\'"-]', '', text)
    return text.strip()

def process_pdf(file_path: str) -> dict:
    """
    PDF 파일에서 텍스트를 추출하고 정제하여 메타데이터와 함께 반환합니다.
    """
    filename = os.path.basename(file_path)
    
    # 네이밍 규칙(카테고리_저자_연도_키워드.pdf)에서 메타데이터 추출 시도
    category, author, year = "unknown", "unknown", "unknown"
    parts = filename.replace('.pdf', '').split('_')
    if len(parts) >= 3:
        category, author, year = parts[0], parts[1], parts[2]
        
    doc = fitz.open(file_path)
    full_text = []
    
    for page in doc:
        text = page.get_text("text")
        cleaned = clean_text(text)
        if len(cleaned) > 50:  # 너무 짧은 페이지(목차나 표지)는 무시
            full_text.append(cleaned)
            
    doc.close()
    
    return {
        "filename": filename,
        "metadata": {
            "category": category,
            "author": author,
            "year": year
        },
        "content": "\n\n".join(full_text)
    }

def main():
    if not os.path.exists(RAW_DIR):
        print(f"Error: {RAW_DIR} 폴더가 없습니다.")
        return
        
    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)
        
    pdf_files = [f for f in os.listdir(RAW_DIR) if f.endswith('.pdf')]
    
    if not pdf_files:
        print(f"[{RAW_DIR}] 폴더에 처리할 PDF 파일이 없습니다.")
        return
        
    # 상태 추적을 위한 파일
    TRACK_FILE = os.path.join(PROCESSED_DIR, 'processed_files.json')
    processed_files = []
    if os.path.exists(TRACK_FILE):
        with open(TRACK_FILE, 'r') as f:
            processed_files = json.load(f)
            
    print(f"총 {len(pdf_files)}개의 PDF 중, 이미 처리된 {len(processed_files)}개를 제외하고 진행합니다...")
    
    for file in tqdm(pdf_files):
        if file in processed_files:
            continue
            
        file_path = os.path.join(RAW_DIR, file)
        try:
            processed_data = process_pdf(file_path)
            
            # JSON 형태로 저장
            out_filename = file.replace('.pdf', '.json')
            out_path = os.path.join(PROCESSED_DIR, out_filename)
            
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, ensure_ascii=False, indent=2)
                
            processed_files.append(file)
            # 중간중간 상태 저장 (만약 중간에 뻗어도 재개 가능)
            with open(TRACK_FILE, 'w') as f:
                json.dump(processed_files, f)
                
        except Exception as e:
            print(f"Error processing {file} (Skipping): {str(e)}")
            
    print("전처리 완료! 결과물이 data/processed/ 폴더에 저장되었습니다.")

if __name__ == "__main__":
    main()
