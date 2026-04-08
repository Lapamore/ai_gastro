"""
Утилиты безопасности для локальной авторизации:
- access JWT
- refresh token
- хеширование и проверка паролей
"""
import base64
import hashlib
import hmac
import logging
import re
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
PASSWORD_SCHEME = "scrypt"
SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def create_jwt_token(
    user_id: str,
    secret: str,
    display_name: Optional[str] = None,
    expires_minutes: int = 30,
) -> str:
    """Создаёт короткоживущий access JWT токен."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    if display_name:
        payload["name"] = display_name
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str, secret: str) -> Optional[dict]:
    """Декодирует и валидирует access JWT токен."""
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            logger.warning("JWT токен имеет неверный тип")
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT токен истёк")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Невалидный JWT токен: {e}")
        return None


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_REGEX.match(normalize_email(email)))


def validate_password_strength(password: str) -> Optional[str]:
    if len(password) < 8:
        return "Пароль должен содержать минимум 8 символов"
    if len(password) > 128:
        return "Пароль слишком длинный"
    if not re.search(r"[A-ZА-Я]", password):
        return "Пароль должен содержать хотя бы одну заглавную букву"
    if not re.search(r"[a-zа-я]", password):
        return "Пароль должен содержать хотя бы одну строчную букву"
    if not re.search(r"\d", password):
        return "Пароль должен содержать хотя бы одну цифру"
    return None


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return (
        f"{PASSWORD_SCHEME}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}$"
        f"{_b64encode(salt)}${_b64encode(derived_key)}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, n_value, r_value, p_value, salt_b64, hash_b64 = stored_hash.split("$", 5)
        if scheme != PASSWORD_SCHEME:
            return False

        salt = _b64decode(salt_b64)
        expected = _b64decode(hash_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_value),
            r=int(r_value),
            p=int(p_value),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except Exception as exc:
        logger.warning("Ошибка проверки пароля: %s", exc)
        return False


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_refresh_token_expiry(days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
