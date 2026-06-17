import os
import time
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
from api.value_cards import router as value_card_router
from api.intentions import router as intention_router
from api.auth import router as auth_router
from api.report import router as report_router
from services.observability import log_event, normalize_request_id, reset_request_id, set_request_id
from services.origin_security import cors_allowed_origins

app = FastAPI(title="Logos-Log API", description="AI 챗봇을 위한 백엔드 API 서버")


@app.middleware("http")
async def request_context_middleware(request, call_next):
    request_id = normalize_request_id(request.headers.get("x-request-id"))
    token = set_request_id(request_id)
    started_at = time.monotonic()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        log_event(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=round((time.monotonic() - started_at) * 1000),
        )
        return response
    except Exception as exc:
        log_event(
            "request_unhandled_error",
            level="error",
            method=request.method,
            path=request.url.path,
            error_type=type(exc).__name__,
            latency_ms=round((time.monotonic() - started_at) * 1000),
        )
        raise
    finally:
        reset_request_id(token)


# 프론트엔드 연동을 위한 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth_router, prefix="/api", tags=["Auth"])
app.include_router(chat_router, prefix="/api", tags=["Chat"])
app.include_router(journal_router, prefix="/api", tags=["Journals"])
app.include_router(value_card_router, prefix="/api", tags=["Value Cards"])
app.include_router(intention_router, prefix="/api", tags=["Intentions"])
app.include_router(report_router, prefix="/api", tags=["Report"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Logos-Log API Server"}


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "logos_log",
        "version": os.getenv("APP_VERSION", "dev"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
