"""
일기/대화 본문 at-rest 암호화 — AES-256-GCM (인증 암호화).

ENCRYPTION_KEY(.env, 32바이트 base64)로 애플리케이션 계층에서 암·복호화한다.
DB에는 'enc:v1:<base64(nonce+ciphertext)>' 형태의 암호문만 저장되므로, DB가 유출되어도
키 없이는 본문을 복원할 수 없다.

레거시 호환: 접두사가 없는 값(암호화 도입 이전에 저장된 평문)은 복호화 시 그대로 반환한다.
→ 데이터 마이그레이션 없이, 새로 쓰는 본문부터 점진적으로 암호화된다.

키 관리: 현재는 환경변수(.env). 운영 환경에서는 KMS/Vault 분리 보관으로 강화할 수 있다(PRD §5.1).
"""
import os
import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_PREFIX = "enc:v1:"
_NONCE_BYTES = 12
_cipher = None


def _get_cipher() -> AESGCM:
    """ENCRYPTION_KEY 로 AESGCM 인스턴스를 지연 생성(캐시). 키 누락/오류 시 명확히 실패."""
    global _cipher
    if _cipher is None:
        raw = os.getenv("ENCRYPTION_KEY")
        if not raw:
            raise RuntimeError("ENCRYPTION_KEY 환경변수가 설정되지 않았습니다. (일기 본문 암호화에 필요)")
        try:
            key = base64.urlsafe_b64decode(raw)
        except Exception as e:
            raise RuntimeError(f"ENCRYPTION_KEY base64 디코드 실패: {e}")
        if len(key) != 32:
            raise RuntimeError(f"ENCRYPTION_KEY 는 32바이트(AES-256)여야 합니다. 현재 {len(key)}바이트.")
        _cipher = AESGCM(key)
    return _cipher


def encrypt(plaintext):
    """문자열을 암호화해 'enc:v1:...' 토큰을 반환. None·빈문자열·비문자열은 그대로 반환."""
    if not isinstance(plaintext, str) or plaintext == "":
        return plaintext
    nonce = os.urandom(_NONCE_BYTES)
    ct = _get_cipher().encrypt(nonce, plaintext.encode("utf-8"), None)
    return _PREFIX + base64.urlsafe_b64encode(nonce + ct).decode("ascii")


def decrypt(value):
    """'enc:v1:...' 토큰을 복호화. 접두사가 없으면(레거시 평문) 그대로 반환."""
    if not isinstance(value, str) or not value.startswith(_PREFIX):
        return value
    raw = base64.urlsafe_b64decode(value[len(_PREFIX):])
    nonce, ct = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    return _get_cipher().decrypt(nonce, ct, None).decode("utf-8")
