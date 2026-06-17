import datetime
import asyncio
import os
import secrets
import hashlib
import bcrypt
import jwt
from fastapi import APIRouter, Cookie, HTTPException, Depends, Request, Response
from pydantic import BaseModel, EmailStr
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError
from starlette.concurrency import run_in_threadpool
from db import get_db
from api.deps import JWT_SECRET, ALGORITHM
from services.observability import log_event, safe_hash
from services.origin_security import enforce_trusted_origin
from services.rate_limit import client_identifier, enforce_env_rate_limit

router = APIRouter()

# JWT Config (시크릿/알고리즘은 api.deps 에서 단일 소스로 관리)
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7 # 1주일 유지
REFRESH_TOKEN_EXPIRE_DAYS = 30
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "logos_refresh_token")


def utc_now():
    return datetime.datetime.now(datetime.UTC)

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
    expire = utc_now() + datetime.timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": expire,
        "token_type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def refresh_token_expiry() -> datetime.datetime:
    return utc_now() + datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)


def new_refresh_jti() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_jti(jti: str) -> str:
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


def create_refresh_token(
    user_id: str,
    email: str,
    jti: str | None = None,
    family_id: str | None = None,
    expires_at: datetime.datetime | None = None,
) -> str:
    token_jti = jti or new_refresh_jti()
    token_family_id = family_id or new_refresh_jti()
    expire = expires_at or refresh_token_expiry()
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": expire,
        "jti": token_jti,
        "family_id": token_family_id,
        "token_type": "refresh",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def set_refresh_cookie(response: Response, token: str):
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=get_bool_env("REFRESH_COOKIE_SECURE", False),
        samesite=os.getenv("REFRESH_COOKIE_SAMESITE", "lax"),
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/auth",
    )


def clear_refresh_cookie(response: Response):
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/auth",
        secure=get_bool_env("REFRESH_COOKIE_SECURE", False),
        samesite=os.getenv("REFRESH_COOKIE_SAMESITE", "lax"),
    )


def decode_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="refresh token이 만료되었습니다.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="유효하지 않은 refresh token입니다.")

    if payload.get("token_type") != "refresh":
        raise HTTPException(status_code=401, detail="refresh token이 아닙니다.")
    if not payload.get("user_id") or not payload.get("email") or not payload.get("jti") or not payload.get("family_id"):
        raise HTTPException(status_code=401, detail="refresh token 정보가 불완전합니다.")
    return payload


def issue_refresh_token(db, user_id: str, email: str, family_id: str | None = None) -> str:
    jti = new_refresh_jti()
    session_family_id = family_id or new_refresh_jti()
    expires_at = refresh_token_expiry()
    token = create_refresh_token(
        user_id,
        email,
        jti=jti,
        family_id=session_family_id,
        expires_at=expires_at,
    )

    db.refresh_tokens.insert_one({
        "user_id": user_id,
        "email": email,
        "jti_hash": hash_refresh_jti(jti),
        "family_id": session_family_id,
        "created_at": utc_now(),
        "expires_at": expires_at,
        "revoked_at": None,
        "revoked_reason": None,
    })
    return token


def user_lookup_id(user_id: str):
    try:
        return ObjectId(user_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=401, detail="refresh token 사용자 정보가 올바르지 않습니다.")


def revoke_refresh_family(db, user_id: str, family_id: str, reason: str):
    db.refresh_tokens.update_many(
        {
            "user_id": user_id,
            "family_id": family_id,
            "revoked_at": None,
        },
        {
            "$set": {
                "revoked_at": utc_now(),
                "revoked_reason": reason,
            }
        },
    )


def rotate_refresh_token(db, payload: dict) -> tuple[str, str]:
    user_id = payload["user_id"]
    jti_hash = hash_refresh_jti(payload["jti"])
    now = utc_now()

    consumed_session = db.refresh_tokens.find_one_and_update(
        {
            "user_id": user_id,
            "jti_hash": jti_hash,
            "revoked_at": None,
            "expires_at": {"$gt": now},
        },
        {
            "$set": {
                "revoked_at": now,
                "revoked_reason": "rotated",
            }
        },
        return_document=ReturnDocument.BEFORE,
    )
    if not consumed_session:
        stale_session = db.refresh_tokens.find_one(
            {
                "user_id": user_id,
                "jti_hash": jti_hash,
            },
            {"family_id": 1},
        )
        if stale_session and stale_session.get("family_id"):
            revoke_refresh_family(db, user_id, stale_session["family_id"], "reuse_detected")
        raise HTTPException(status_code=401, detail="refresh session이 유효하지 않습니다.")

    user = db.users.find_one(
        {"_id": user_lookup_id(user_id)},
        {"email": 1},
    )
    if not user:
        raise HTTPException(status_code=401, detail="사용자 계정을 찾을 수 없습니다.")

    email = user.get("email") or payload["email"]
    family_id = consumed_session.get("family_id") or payload["family_id"]
    return issue_refresh_token(db, user_id, email, family_id=family_id), email


def revoke_refresh_token(db, payload: dict, reason: str):
    db.refresh_tokens.update_one(
        {
            "user_id": payload["user_id"],
            "jti_hash": hash_refresh_jti(payload["jti"]),
            "revoked_at": None,
        },
        {
            "$set": {
                "revoked_at": utc_now(),
                "revoked_reason": reason,
            }
        },
    )


def enforce_auth_rate_limit(request: Request, email: str, scope: str):
    enforce_env_rate_limit(
        scope=scope,
        identifier=client_identifier(request, email),
        limit_env="AUTH_RATE_LIMIT_PER_MINUTE",
        default_limit=8,
        window_env="AUTH_RATE_LIMIT_WINDOW_SECONDS",
        default_window_seconds=60,
    )


@router.post("/auth/signup")
async def signup(credentials: UserCredentials, request: Request, response: Response):
    """
    MongoDB에 새 사용자를 가입시키고, 패스워드를 해싱하여 안전하게 저장합니다.
    """
    db = get_db()
    email = normalize_email(credentials.email)
    enforce_trusted_origin(request)
    enforce_auth_rate_limit(request, email, "auth_signup")

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
            "created_at": utc_now()
        }

        result = await run_in_threadpool(db.users.insert_one, user_doc)
        user_id = str(result.inserted_id)
        token = create_jwt_token(user_id, email)
        refresh_token = await run_in_threadpool(issue_refresh_token, db, user_id, email)
        set_refresh_cookie(response, refresh_token)
        
        return {
            "message": "회원가입이 완료되었습니다.",
            "access_token": token,
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
        log_event("auth_signup_error", level="error", email_hash=safe_hash(email), error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="회원가입 처리 중 오류가 발생했습니다.")

@router.post("/auth/login")
async def login(credentials: UserCredentials, request: Request, response: Response):
    """
    비밀번호를 검증하고 세션 유지를 위한 JWT 액세스 토큰을 반환합니다.
    """
    db = get_db()
    email = normalize_email(credentials.email)
    enforce_trusted_origin(request)
    enforce_auth_rate_limit(request, email, "auth_login")
    
    try:
        user = await run_in_threadpool(
            db.users.find_one,
            {"email": email},
            {"email": 1, "password": 1}
        )
    except PyMongoError:
        log_event("auth_login_db_error", level="error", email_hash=safe_hash(email))
        raise HTTPException(status_code=503, detail="데이터베이스 연결이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.")
    if not user:
        log_event("auth_login_failed", level="warning", reason="unknown_email", email_hash=safe_hash(email))
        raise HTTPException(status_code=400, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
        
    is_valid = await run_in_threadpool(
        verify_password,
        credentials.password,
        user.get("password", "")
    )
    if not is_valid:
        log_event("auth_login_failed", level="warning", reason="invalid_password", email_hash=safe_hash(email))
        raise HTTPException(status_code=400, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
        
    user_id = str(user["_id"])
    token = create_jwt_token(user_id, user["email"])
    refresh_token = await run_in_threadpool(issue_refresh_token, db, user_id, user["email"])
    set_refresh_cookie(response, refresh_token)
    
    return {
        "access_token": token,
        "user": {
            "id": user_id,
            "email": user["email"]
        }
    }


@router.post("/auth/refresh")
async def refresh_access_token(
    request: Request,
    response: Response,
    refresh_token: str = Cookie(None, alias=REFRESH_COOKIE_NAME),
):
    enforce_trusted_origin(request)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="refresh token이 없습니다.")

    try:
        payload = decode_refresh_token(refresh_token)
        db = get_db()
        rotated_refresh_token, email = await run_in_threadpool(rotate_refresh_token, db, payload)
    except HTTPException as exc:
        log_event(
            "auth_refresh_failed",
            level="warning",
            status_code=exc.status_code,
            reason=str(exc.detail),
        )
        clear_refresh_cookie(response)
        raise
    except (PyMongoError, ValueError) as exc:
        log_event("auth_refresh_error", level="error", error_type=type(exc).__name__)
        clear_refresh_cookie(response)
        raise HTTPException(status_code=503, detail="세션 확인이 지연되고 있습니다. 다시 로그인해 주세요.")

    user_id = payload["user_id"]
    access_token = create_jwt_token(user_id, email)
    set_refresh_cookie(response, rotated_refresh_token)

    return {
        "access_token": access_token,
        "user": {
            "id": user_id,
            "email": email,
        },
    }


@router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    refresh_token: str = Cookie(None, alias=REFRESH_COOKIE_NAME),
):
    enforce_trusted_origin(request)
    if refresh_token:
        try:
            payload = decode_refresh_token(refresh_token)
            db = get_db()
            await run_in_threadpool(revoke_refresh_token, db, payload, "logout")
        except Exception as e:
            log_event("auth_logout_revoke_skipped", level="warning", error_type=type(e).__name__)
    clear_refresh_cookie(response)
    return {"message": "로그아웃되었습니다."}
