import os
import json
import re

EMBEDDING_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/embeddings'))

def fix_metadata(filename, metadata):
    # 4자리 연도 찾기 (예: _2021_ 또는 _1998_)
    match = re.search(r'_(19\d{2}|20\d{2})_', filename)
    if match:
        year = match.group(1)
        prefix = filename[:match.start()]
        
        categories = ["positive_psych", "logotherapy", "cbt", "sdt"]
        matched_cat = None
        for cat in categories:
            if prefix.startswith(cat):
                matched_cat = cat
                break
                
        if matched_cat:
            category = matched_cat
            author_raw = prefix[len(matched_cat):].strip('_')
            author = author_raw.replace('_', ' ').title()
        else:
            parts = prefix.split('_')
            category = parts[0]
            author = " ".join(parts[1:]).title()
            
        metadata["category"] = category
        metadata["author"] = author
        metadata["year"] = year
    else:
        # 연도를 찾을 수 없으면 기존 쪼개기 보강
        parts = filename.replace('_embedded.json', '').split('_')
        if len(parts) >= 3:
            metadata["category"] = parts[0]
            metadata["author"] = parts[1].replace('_', ' ').title()
            metadata["year"] = parts[2]
            
    return metadata

def main():
    json_files = [f for f in os.listdir(EMBEDDING_DIR) if f.endswith('_embedded.json')]
    print(f"보정할 로컬 임베딩 파일 개수: {len(json_files)}")
    
    modified_count = 0
    for file in json_files:
        file_path = os.path.join(EMBEDDING_DIR, file)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        is_modified = False
        for record in data:
            orig_meta = record.get("metadata", {})
            orig_author = orig_meta.get("author")
            orig_year = orig_meta.get("year")
            
            # 보정 실행
            fixed_meta = fix_metadata(file, dict(orig_meta))
            
            # 변경이 발생했는지 감지
            if fixed_meta.get("author") != orig_author or fixed_meta.get("year") != orig_year:
                record["metadata"] = fixed_meta
                is_modified = True
                
        if is_modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            modified_count += 1
            
    print(f"총 {modified_count}개 파일의 메타데이터를 보정하여 다시 저장했습니다.")

if __name__ == "__main__":
    main()
