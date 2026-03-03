"""
JWT утилиты для авторизации
"""
import jwt
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Время жизни токена — 30 дней
TOKEN_EXPIRE_DAYS = 30


def create_jwt_token(user_id: str, secret: str, display_name: Optional[str] = None) -> str:
    """Создаёт JWT токен для пользователя"""
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    if display_name:
        payload["name"] = display_name
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_jwt_token(token: str, secret: str) -> Optional[dict]:
    """Декодирует и валидирует JWT токен. Возвращает payload или None."""
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT токен истёк")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Невалидный JWT токен: {e}")
        return None
