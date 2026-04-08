import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from src.api.auth_dependency import get_current_user_id
from src.core.auth import (
    create_jwt_token,
    create_refresh_token,
    get_refresh_token_expiry,
    hash_password,
    hash_refresh_token,
    is_valid_email,
    normalize_email,
    validate_password_strength,
    verify_password,
)
from src.core.models.users.UserModel import User
from src.infrastructure.dependencies.Config import AppConfig
from src.infrastructure.dependencies.Dependencies import get_app_config, get_db_service_dependency
from src.infrastructure.interfaces.IDataBase import AbstractDBService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthUserResponse(BaseModel):
    id: str
    display_name: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: AuthUserResponse


def _build_user_response(user: User) -> AuthUserResponse:
    display_name = (user.username or "").strip() or (user.email or "").split("@")[0] or "User"
    return AuthUserResponse(
        id=user.id,
        display_name=display_name,
        email=user.email,
        avatar_url=user.avatar_url,
    )


def _set_refresh_cookie(response: Response, refresh_token: str, config: AppConfig) -> None:
    response.set_cookie(
        key=config.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=config.cookie_secure,
        samesite=config.cookie_samesite,
        max_age=config.refresh_token_expire_days * 24 * 60 * 60,
        expires=config.refresh_token_expire_days * 24 * 60 * 60,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response, config: AppConfig) -> None:
    response.delete_cookie(
        key=config.refresh_cookie_name,
        httponly=True,
        secure=config.cookie_secure,
        samesite=config.cookie_samesite,
        path="/api/auth",
    )


async def _issue_session(
    *,
    response: Response,
    user: User,
    request: Request,
    config: AppConfig,
    db_service: AbstractDBService,
) -> AuthResponse:
    access_token = create_jwt_token(
        user_id=user.id,
        secret=config.jwt_secret,
        display_name=user.username,
        expires_minutes=config.access_token_expire_minutes,
    )
    refresh_token = create_refresh_token()
    await db_service.store_refresh_token(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=get_refresh_token_expiry(config.refresh_token_expire_days),
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    _set_refresh_cookie(response, refresh_token, config)
    return AuthResponse(
        access_token=access_token,
        expires_in=config.access_token_expire_minutes * 60,
        user=_build_user_response(user),
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    config: AppConfig = Depends(get_app_config),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    username = payload.username.strip()
    email = normalize_email(payload.email)

    if len(username) < 2:
        raise HTTPException(status_code=400, detail="Имя должно содержать минимум 2 символа")
    if len(username) > 50:
        raise HTTPException(status_code=400, detail="Имя слишком длинное")
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Введите корректный email")

    password_error = validate_password_strength(payload.password)
    if password_error:
        raise HTTPException(status_code=400, detail=password_error)

    existing_user = await db_service.get_user_by_email(email)
    if existing_user:
        if existing_user.password_hash:
            raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует")

        user = await db_service.set_local_credentials(
            user_id=existing_user.id,
            username=username,
            password_hash=hash_password(payload.password),
        )
        logger.info("Пользователь %s переведён на локальную авторизацию", user.id)
    else:
        user = await db_service.create_local_user(
            username=username,
            email=email,
            password_hash=hash_password(payload.password),
        )
        logger.info("Создан локальный пользователь %s", user.id)
    return await _issue_session(
        response=response,
        user=user,
        request=request,
        config=config,
        db_service=db_service,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    config: AppConfig = Depends(get_app_config),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    email = normalize_email(payload.email)
    invalid_credentials_error = HTTPException(
        status_code=401,
        detail="Неверный email или пароль",
    )

    user = await db_service.get_user_by_email(email)
    if not user or not user.password_hash or user.auth_provider != "local":
        await asyncio.sleep(0.3)
        raise invalid_credentials_error

    if not verify_password(payload.password, user.password_hash):
        await asyncio.sleep(0.3)
        raise invalid_credentials_error

    return await _issue_session(
        response=response,
        user=user,
        request=request,
        config=config,
        db_service=db_service,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None, alias="gastro_refresh_token"),
    config: AppConfig = Depends(get_app_config),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    cookie_value = refresh_token or request.cookies.get(config.refresh_cookie_name)
    if not cookie_value:
        _clear_refresh_cookie(response, config)
        raise HTTPException(status_code=401, detail="Сессия истекла")

    token_hash = hash_refresh_token(cookie_value)
    user = await db_service.get_user_by_refresh_token(token_hash)
    if not user:
        _clear_refresh_cookie(response, config)
        raise HTTPException(status_code=401, detail="Сессия истекла")

    await db_service.revoke_refresh_token(token_hash)
    return await _issue_session(
        response=response,
        user=user,
        request=request,
        config=config,
        db_service=db_service,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None, alias="gastro_refresh_token"),
    config: AppConfig = Depends(get_app_config),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    cookie_value = refresh_token or request.cookies.get(config.refresh_cookie_name)
    if cookie_value:
        await db_service.revoke_refresh_token(hash_refresh_token(cookie_value))
    _clear_refresh_cookie(response, config)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=AuthUserResponse)
async def me(
    user_id: str = Depends(get_current_user_id),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    user = await db_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return _build_user_response(user)
