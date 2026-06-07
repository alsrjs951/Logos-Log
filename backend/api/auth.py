import datetime
import asyncio
import os
import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError
from starlette.concurrency import run_in_threadpool
from db import get_db
from api.deps import JWT_SECRET, ALGORITHM

router = APIRouter()

# JWT Config (시크릿/알고리즘은 api.deps 에서 단일 소스로 관리)
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7 # 1주일 유지

def get_bcrypt_rounds() -> int:
    try:
        return max(10, min(14, int(os.getenv("BCRYPT_ROUNDS", "12"))))
    except ValueError:
        return 12

BCRYPT_ROUNDS = get_bcrypt_rounds()

class UserCredentials(BaseModel):
    email: EmailStr
    password: str

def normalize_email(email: EmailStr) -> str:
    return str(email).strip().lower()

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def create_jwt_token(user_id: str, email: str) -> str:
    expire = datetime.datetime.utcnow() + datetime.timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": expire
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

@router.post("/auth/signup")
async def signup(credentials: UserCredentials):
    """
    MongoDB에 새 사용자를 가입시키고, 패스워드를 해싱하여 안전하게 저장합니다.
    """
    db = get_db()
    email = normalize_email(credentials.email)

    # 비밀번호 최소 길이 서버 측 강제 (프론트 검증 우회 방지)
    if len(credentials.password) < 8:
        raise HTTPException(status_code=400, detail="비밀번호는 최소 8자 이상이어야 합니다.")

    try:
        # DB 왕복과 bcrypt 해싱을 겹쳐서 신규 가입의 체감 대기 시간을 줄인다.
        existing_user, hashed = await asyncio.gather(
            run_in_threadpool(db.users.find_one, {"email": email}, {"_id": 1}),
            run_in_threadpool(hash_password, credentials.password),
        )
        if existing_user:
            raise HTTPException(status_code=400, detail="이미 등록된 이메일 계정입니다.")

        user_doc = {
            "email": email,
            "password": hashed,
            "created_at": datetime.datetime.utcnow()
        }

        result = await run_in_threadpool(db.users.insert_one, user_doc)
        user_id = str(result.inserted_id)
        token = create_jwt_token(user_id, email)
        
        return {
            "message": "회원가입이 완료되었습니다.",
            "access_token": token,
            "refresh_token": token,
            "user": {
                "id": user_id,
                "email": email
            }
        }
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="이미 등록된 이메일 계정입니다.")
    except PyMongoError:
        raise HTTPException(status_code=503, detail="데이터베이스 연결이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[auth] signup error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="회원가입 처리 중 오류가 발생했습니다.")

@router.post("/auth/login")
async def login(credentials: UserCredentials):
    """
    비밀번호를 검증하고 세션 유지를 위한 JWT 액세스 토큰을 반환합니다.
    """
    db = get_db()
    email = normalize_email(credentials.email)
    
    try:
        user = await run_in_threadpool(
            db.users.find_one,
            {"email": email},
            {"email": 1, "password": 1}
        )
    except PyMongoError:
        raise HTTPException(status_code=503, detail="데이터베이스 연결이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.")
    if not user:
        raise HTTPException(status_code=400, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
        
    is_valid = await run_in_threadpool(
        verify_password,
        credentials.password,
        user.get("password", "")
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
        
    user_id = str(user["_id"])
    token = create_jwt_token(user_id, user["email"])
    
    return {
        "access_token": token,
        "refresh_token": token,  # 단순화를 위해 리프레시 토큰도 동일하게 전달
        "user": {
            "id": user_id,
            "email": user["email"]
        }
    }
