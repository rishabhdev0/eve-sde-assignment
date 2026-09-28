from datetime import datetime, timedelta, timezone
import uuid
from passlib.context import CryptContext
from jose import jwt, JWTError
from itsdangerous import URLSafeTimedSerializer
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
reset_serializer = URLSafeTimedSerializer(settings.JWT_SECRET)
verify_serializer = URLSafeTimedSerializer(settings.JWT_SECRET)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(subject: str, expires_delta: timedelta, token_type: str) -> tuple[str, str]:
    """Returns (token, jti) — jti lets refresh tokens be individually revoked."""
    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "type": token_type, "jti": jti, "iat": now, "exp": now + expires_delta}
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def create_access_token(user_id: str) -> str:
    token, _ = create_token(user_id, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access")
    return token


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise ValueError("invalid_token")
    if payload.get("type") != expected_type:
        raise ValueError("wrong_token_type")
    return payload


def generate_reset_token(email: str) -> str:
    return reset_serializer.dumps(email, salt="password-reset")


def verify_reset_token(token: str) -> str:
    return reset_serializer.loads(token, salt="password-reset", max_age=settings.RESET_TOKEN_EXPIRE_MINUTES * 60)


def generate_verify_token(email: str) -> str:
    return verify_serializer.dumps(email, salt="email-verify")


def verify_verify_token(token: str) -> str:
    return verify_serializer.loads(token, salt="email-verify", max_age=settings.VERIFY_TOKEN_EXPIRE_HOURS * 3600)