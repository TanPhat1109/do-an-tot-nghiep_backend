import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from fastapi.security import HTTPBearer

import config
import models
from database import get_db

_ph = PasswordHasher()
# Hash giả để login tốn thời gian tương đương khi email không tồn tại
_DUMMY_HASH = _ph.hash("dummy-password-for-timing")

bearer_scheme = HTTPBearer(auto_error=False)


# ---------- Mật khẩu ----------
def _is_legacy_sha256(hashed: str) -> bool:
    return len(hashed) == 64 and all(c in "0123456789abcdefABCDEF" for c in hashed)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Hỗ trợ hash SHA-256 cũ để user cũ vẫn đăng nhập được (sẽ được nâng cấp khi login)
    if _is_legacy_sha256(hashed_password):
        legacy = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy, hashed_password.lower())
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed_password: str) -> bool:
    return _is_legacy_sha256(hashed_password) or _ph.check_needs_rehash(hashed_password)


def fake_verify() -> None:
    """Gọi khi không tìm thấy user, để chống dò email qua thời gian phản hồi."""
    verify_password("x", _DUMMY_HASH)


# ---------- JWT ----------
def create_access_token(data: dict, expires_minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    minutes = expires_minutes or config.ACCESS_TOKEN_EXPIRE_MINUTES
    payload = {**data, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Ném jwt.PyJWTError nếu token sai, giả mạo hoặc hết hạn."""
    return jwt.decode(
        token,
        config.SECRET_KEY,
        algorithms=[config.ALGORITHM],
        options={"require": ["exp", "sub"]},
    )


# ---------- Dependencies ----------
def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise credentials_error
    try:
        payload = decode_access_token(creds.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise credentials_error

    user = db.get(models.User, user_id)
    if user is None:
        raise credentials_error
    return user  # role luôn lấy từ DB, không tin claim trong token


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != models.UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không đủ quyền truy cập")
    return user