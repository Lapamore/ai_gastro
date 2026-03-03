"""
Роуты авторизации через Яндекс ID (OAuth 2.0)
"""
import logging
import httpx
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse

from src.infrastructure.dependencies.Config import AppConfig
from src.infrastructure.dependencies.Dependencies import get_app_config, get_db_service_dependency
from src.infrastructure.interfaces.IDataBase import AbstractDBService
from src.core.auth import create_jwt_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

YANDEX_AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
YANDEX_USERINFO_URL = "https://login.yandex.ru/info"


@router.get("/yandex")
async def yandex_login(config: AppConfig = Depends(get_app_config)):
    """Перенаправляет пользователя на страницу авторизации Яндекса"""
    if not config.yandex_client_id:
        raise HTTPException(status_code=500, detail="YANDEX_CLIENT_ID не настроен")

    redirect_uri = f"{config.frontend_url}/auth/callback"
    url = (
        f"{YANDEX_AUTHORIZE_URL}"
        f"?response_type=code"
        f"&client_id={config.yandex_client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&force_confirm=yes"
    )
    return RedirectResponse(url=url)


@router.post("/yandex/callback")
async def yandex_callback(
    code: str = Query(...),
    config: AppConfig = Depends(get_app_config),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    """
    Принимает authorization code от Яндекса, обменивает на токен,
    получает информацию о пользователе, создаёт/находит в БД, возвращает JWT.
    """
    if not config.yandex_client_id or not config.yandex_client_secret:
        raise HTTPException(status_code=500, detail="Yandex OAuth не настроен")

    redirect_uri = f"{config.frontend_url}/auth/callback"

    # 1. Обмениваем code на access_token
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                YANDEX_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": config.yandex_client_id,
                    "client_secret": config.yandex_client_secret,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if token_response.status_code != 200:
            logger.error(f"Yandex token error: {token_response.text}")
            raise HTTPException(status_code=400, detail="Не удалось получить токен от Яндекса")

        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Яндекс не вернул access_token")

    except httpx.HTTPError as e:
        logger.error(f"HTTP error при обмене кода: {e}")
        raise HTTPException(status_code=502, detail="Ошибка связи с Яндексом")

    # 2. Получаем информацию о пользователе
    try:
        async with httpx.AsyncClient() as client:
            user_info_response = await client.get(
                YANDEX_USERINFO_URL,
                params={"format": "json"},
                headers={"Authorization": f"OAuth {access_token}"},
            )

        if user_info_response.status_code != 200:
            logger.error(f"Yandex userinfo error: {user_info_response.text}")
            raise HTTPException(status_code=400, detail="Не удалось получить данные пользователя")

        yandex_user = user_info_response.json()
        yandex_id = yandex_user.get("id")
        display_name = yandex_user.get("display_name") or yandex_user.get("real_name") or "User"
        email = yandex_user.get("default_email", "")
        avatar_id = yandex_user.get("default_avatar_id", "")

        if not yandex_id:
            raise HTTPException(status_code=400, detail="Яндекс не вернул id пользователя")

    except httpx.HTTPError as e:
        logger.error(f"HTTP error при получении userinfo: {e}")
        raise HTTPException(status_code=502, detail="Ошибка связи с Яндексом")

    # 3. Создаём или находим пользователя в БД
    user = await db_service.get_or_create_user_by_yandex(
        yandex_id=yandex_id,
        display_name=display_name,
        email=email,
        avatar_id=avatar_id,
    )

    # 4. Генерируем JWT
    jwt_token = create_jwt_token(
        user_id=user.id,
        secret=config.jwt_secret,
        display_name=display_name,
    )

    logger.info(f"Пользователь авторизован: {display_name} (yandex_id={yandex_id}, user_id={user.id})")

    return {
        "token": jwt_token,
        "user": {
            "id": user.id,
            "display_name": display_name,
            "email": email,
            "avatar_url": f"https://avatars.yandex.net/get-yapic/{avatar_id}/islands-200" if avatar_id else None,
        },
    }
