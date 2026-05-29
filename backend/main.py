import os
from dotenv import load_dotenv

# .env 파일 탐색: backend/ 우선, 없으면 프로젝트 루트(backend의 상위 디렉토리) 탐색
_backend_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_backend_dir)

_env_backend = os.path.join(_backend_dir, '.env')
_env_root = os.path.join(_root_dir, '.env')

if os.path.exists(_env_backend):
    load_dotenv(_env_backend)
elif os.path.exists(_env_root):
    load_dotenv(_env_root)
else:
    load_dotenv()  # 기본 탐색 (현재 작업 디렉토리)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.chat import router as chat_router
from api.journals import router as journal_router

app = FastAPI(title="Logos-Log API", description="AI 챗봇을 위한 백엔드 API 서버")

# 프론트엔드 연동을 위한 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 보안을 위해 향후 프론트엔드 URL로 변경
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(chat_router, prefix="/api", tags=["Chat"])
app.include_router(journal_router, prefix="/api", tags=["Journals"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Logos-Log API Server"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
