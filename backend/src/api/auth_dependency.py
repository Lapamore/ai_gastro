"""
Общая зависимость для извлечения user_id из JWT токена.
Используется во всех защищённых роутах.
"""
import logging
from fastapi import Depends, HTTPException, Header
from typing import Optional

from src.infrastructure.dependencies.Config import AppConfig
from src.infrastructure.dependencies.Dependencies import get_app_config
from src.core.auth import decode_jwt_token

logger = logging.getLogger(__name__)


def get_current_user_id(
    authorization: Optional[str] = Header(None),
    config: AppConfig = Depends(get_app_config),
) -> str:
    """
    Извлекает user_id из Authorization: Bearer <token>.
    Если токена нет или он невалидный — 401.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    token = authorization[len("Bearer "):]
    payload = decode_jwt_token(token, config.jwt_secret)

    if payload is None:
        raise HTTPException(status_code=401, detail="Невалидный или истёкший токен")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Токен не содержит user_id")

    return user_id
