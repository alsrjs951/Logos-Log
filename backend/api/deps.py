import os
import jwt
from fastapi import Header, HTTPException, Depends
from db import get_db

# JWT 설정 (auth 모듈 전반의 단일 소스). 안전하지 않은 기본 시크릿으로의 폴백을 금지한다.
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET 환경변수가 설정되지 않았습니다. 안전하지 않은 기본 시크릿으로의 구동을 거부합니다."
    )
ALGORITHM = "HS256"

def get_current_user(authorization: str = Header(None)) -> dict:
    """
    HTTP Header 'Authorization: Bearer <token>'을 디코딩하여 유저 식별자 및 이메일을 반환하는 FastAPI 의존성 함수입니다.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="인증 토큰이 누락되었습니다.")
        
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="올바르지 않은 토큰 포맷입니다. (Bearer <token> 형식)")
        
    token = parts[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        email = payload.get("email")
        token_type = payload.get("token_type", "access")
        
        if not user_id or not email:
            raise HTTPException(status_code=401, detail="토큰 정보가 불완전합니다.")
        if token_type != "access":
            raise HTTPException(status_code=401, detail="access token이 아닙니다.")
            
        return {
            "id": user_id,
            "email": email
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="만료된 토큰입니다.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
