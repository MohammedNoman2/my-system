import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
import jwt
from app.core.config import settings

reset_serializer = URLSafeTimedSerializer(settings.PASSWORD_RESET_SECRET)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = plain_password.encode("utf-8")[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def create_refresh_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def generate_password_reset_token(email: str) -> str:
    return reset_serializer.dumps(email, salt=settings.PASSWORD_RESET_SALT)


def verify_password_reset_token(token: str) -> Optional[str]:
    try:
        email = reset_serializer.loads(
            token,
            salt=settings.PASSWORD_RESET_SALT,
            max_age=settings.PASSWORD_RESET_TOKEN_EXPIRE_SECONDS
        )
        return email
    except (BadSignature, SignatureExpired):
        return None
