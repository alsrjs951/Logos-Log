import datetime
import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from bson import ObjectId
from db import get_db
from api.deps import JWT_SECRET, ALGORITHM

router = APIRouter()

# JWT Config (시크릿/알고리즘은 api.deps 에서 단일 소스로 관리)
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7 # 1주일 유지

class UserCredentials(BaseModel):
    email: EmailStr
    password: str

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
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
    
    # 중복 가입 체크
    existing_user = db.users.find_one({"email": credentials.email.lower()})
    if existing_user:
        raise HTTPException(status_code=400, detail="이미 등록된 이메일 계정입니다.")
        
    hashed = hash_password(credentials.password)
    user_doc = {
        "email": credentials.email.lower(),
        "password": hashed,
        "created_at": datetime.datetime.utcnow()
    }
    
    try:
        result = db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)
        
        return {
            "message": "회원가입이 완료되었습니다.",
            "user": {
                "id": user_id,
                "email": credentials.email.lower()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"회원가입 중 서버 오류 발생: {str(e)}")

@router.post("/auth/login")
async def login(credentials: UserCredentials):
    """
    비밀번호를 검증하고 세션 유지를 위한 JWT 액세스 토큰을 반환합니다.
    """
    db = get_db()
    
    user = db.users.find_one({"email": credentials.email.lower()})
    if not user:
        raise HTTPException(status_code=400, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
        
    if not verify_password(credentials.password, user.get("password", "")):
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
