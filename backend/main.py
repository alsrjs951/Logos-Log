import os
from dotenv import load_dotenv

# load .env before starting the app
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.chat import router as chat_router

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

@app.get("/")
def read_root():
    return {"message": "Welcome to Logos-Log API Server"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
