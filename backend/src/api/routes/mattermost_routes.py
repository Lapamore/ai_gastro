"""
API роуты для интеграции с Mattermost ботом.

Эндпоинты:
- POST /api/mattermost/webhook - обработка outgoing webhook
- POST /api/mattermost/slash/recipe - slash-команда /recipe
- POST /api/mattermost/slash/allergies - slash-команда /allergies
"""
import logging
from fastapi import APIRouter, HTTPException, status, Depends, Form, Request
from typing import Optional

from src.core.models.mattermost.MattermostModels import (
    MattermostWebhookRequest,
    MattermostBotResponse,
)
from src.infrastructure.impl.mattermost.MattermostBotService import MattermostBotService
from src.infrastructure.dependencies.Dependencies import get_mattermost_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mattermost", tags=["Mattermost Bot"])


@router.post("/webhook")
async def handle_webhook(
    request: Request,
    mm_service: MattermostBotService = Depends(get_mattermost_service)
):
    """
    Обработка Outgoing Webhook от Mattermost.
    """
    content_type = request.headers.get("content-type", "")
    logger.info(f"Content-Type: {content_type}")
    
    # Получаем тело запроса
    body = await request.body()
    logger.info(f"Raw body: {body.decode()[:500]}")
    
    # Пробуем как JSON
    try:
        data = await request.json()
    except:
        # Пробуем как form
        data = dict(await request.form())
    
    logger.info(f"Parsed data: {data}")
    
    token = data.get("token", "")
    user_id = data.get("user_id", "")
    user_name = data.get("user_name", "unknown")
    text = data.get("text", "")
    trigger_word = data.get("trigger_word", "")
    
    logger.info(f"Получен webhook от {user_name}: {text[:100] if text else 'empty'}")
    
    # Проверяем токен
    if not mm_service.verify_webhook_token(token):
        logger.warning(f"Неверный токен webhook: {token}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook token"
        )
    
    # Обрабатываем сообщение
    response = await mm_service.process_message(
        user_id=user_id,
        text=text,
        user_name=user_name,
        trigger_word=trigger_word
    )
    
    return response


@router.post("/slash/recipe", response_model=MattermostBotResponse)
async def handle_recipe_command(
    token: str = Form(...),
    team_id: str = Form(...),
    channel_id: str = Form(...),
    user_id: str = Form(...),
    user_name: str = Form(...),
    command: str = Form(...),
    text: str = Form(""),
    response_url: Optional[str] = Form(None),
    mm_service: MattermostBotService = Depends(get_mattermost_service)
):
    """
    Обработка slash-команды /recipe.
    
    Использование:
    - /recipe борщ
    - /recipe пицца маргарита
    - /recipe что приготовить на ужин
    """
    logger.info(f"Slash команда /recipe от {user_name}: {text}")
    
    # Проверяем токен
    if not mm_service.verify_webhook_token(token):
        logger.warning(f"Неверный токен slash команды от {user_name}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid command token"
        )
    
    if not text.strip():
        return MattermostBotResponse(
            text="🍳 **Команда /recipe**\n\n"
                 "Использование: `/recipe [название блюда или вопрос]`\n\n"
                 "**Примеры:**\n"
                 "• `/recipe борщ` — рецепт борща\n"
                 "• `/recipe что приготовить на ужин` — идеи для ужина\n"
                 "• `/recipe паста без глютена` — безглютеновый рецепт\n\n"
                 "💡 Не забудьте указать свои аллергии командой `/allergies`!",
            response_type="ephemeral"
        )
    
    # Получаем рецепт
    response = await mm_service.process_message(
        user_id=user_id,
        text=text,
        user_name=user_name
    )
    
    return response


@router.post("/slash/allergies", response_model=MattermostBotResponse)
async def handle_allergies_command(
    token: str = Form(...),
    team_id: str = Form(...),
    channel_id: str = Form(...),
    user_id: str = Form(...),
    user_name: str = Form(...),
    command: str = Form(...),
    text: str = Form(""),
    response_url: Optional[str] = Form(None),
    mm_service: MattermostBotService = Depends(get_mattermost_service)
):
    """
    Обработка slash-команды /allergies.
    
    Использование:
    - /allergies — показать текущие аллергии
    - /allergies орехи, молоко — установить аллергии
    - /allergies add глютен — добавить аллергию
    - /allergies remove молоко — удалить аллергию
    - /allergies clear — очистить все аллергии
    """
    logger.info(f"Slash команда /allergies от {user_name}: {text}")
    
    # Проверяем токен
    if not mm_service.verify_webhook_token(token):
        logger.warning(f"Неверный токен slash команды от {user_name}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid command token"
        )
    
    text = text.strip()
    
    # Если пустой текст — показываем список
    if not text:
        return mm_service.format_allergies_response(user_id, "list")
    
    # Парсим команду
    parts = text.split(maxsplit=1)
    action = parts[0].lower()
    
    if action == "clear":
        mm_service.clear_user_allergies(user_id)
        return mm_service.format_allergies_response(user_id, "clear")
    
    elif action == "add" and len(parts) > 1:
        allergies = [a.strip() for a in parts[1].split(",")]
        mm_service.add_user_allergies(user_id, allergies)
        return mm_service.format_allergies_response(user_id, "add")
    
    elif action == "remove" and len(parts) > 1:
        allergies = [a.strip() for a in parts[1].split(",")]
        mm_service.remove_user_allergies(user_id, allergies)
        return mm_service.format_allergies_response(user_id, "remove")
    
    else:
        # Если не команда — считаем это списком аллергий для установки
        allergies = [a.strip() for a in text.split(",")]
        mm_service.set_user_allergies(user_id, allergies)
        return mm_service.format_allergies_response(user_id, "set")


@router.get("/health")
async def health_check():
    """Проверка работоспособности Mattermost интеграции"""
    return {
        "status": "ok",
        "service": "mattermost-bot",
        "message": "Гастро-Помощник работает! 🍳"
    }
