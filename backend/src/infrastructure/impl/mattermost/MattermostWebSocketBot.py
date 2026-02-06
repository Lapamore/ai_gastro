"""
WebSocket бот для Mattermost.
Слушает все сообщения и отвечает в личных сообщениях и каналах.
"""
import os
import asyncio
import logging
import httpx
from typing import Optional, Dict, List
from collections import defaultdict

from openai import AsyncOpenAI

from src.infrastructure.impl.mattermost.MattermostWebSocket import MattermostWebSocketClient
from src.infrastructure.dependencies.Config import AppConfig

logger = logging.getLogger(__name__)

# Глобальные переменные
_config: Optional[AppConfig] = None
_ai_client: Optional[AsyncOpenAI] = None
_bot_user_id: Optional[str] = None
_system_prompt: str = ""

# История чатов для каждого пользователя
# Формат: {user_id: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
_chat_history: Dict[str, List[dict]] = defaultdict(list)
MAX_HISTORY_LENGTH = 20  # Максимальное количество сообщений в истории


def _load_system_prompt(file_path: Optional[str]) -> str:
    """Загружает системный промпт из файла"""
    default_prompt = """Ты — Гастро-Помощник, дружелюбный бот для помощи с рецептами.
Отвечай только на вопросы о рецептах, блюдах и кулинарии.
Если спрашивают о чём-то другом — вежливо объясни что ты специализируешься только на рецептах."""
    
    if not file_path or not os.path.exists(file_path):
        return default_prompt
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Ошибка загрузки промпта: {e}")
        return default_prompt


async def get_bot_user_id(mattermost_url: str, bot_token: str) -> Optional[str]:
    """Получает ID пользователя бота"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{mattermost_url}/api/v4/users/me",
                headers={"Authorization": f"Bearer {bot_token}"}
            )
            if response.status_code == 200:
                return response.json().get("id")
    except Exception as e:
        logger.error(f"Ошибка получения ID бота: {e}")
    return None


async def send_message(channel_id: str, message: str) -> bool:
    """Отправляет сообщение в канал через Bot API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{_config.mattermost_url}/api/v4/posts",
                headers={
                    "Authorization": f"Bearer {_config.mattermost_bot_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "channel_id": channel_id,
                    "message": message
                }
            )
            return response.status_code == 201
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        return False


async def get_ai_response(user_id: str, user_message: str) -> str:
    """Получает ответ от AI с учётом истории чата"""
    global _chat_history
    
    # Добавляем сообщение пользователя в историю
    _chat_history[user_id].append({"role": "user", "content": user_message})
    
    # Ограничиваем историю
    if len(_chat_history[user_id]) > MAX_HISTORY_LENGTH:
        _chat_history[user_id] = _chat_history[user_id][-MAX_HISTORY_LENGTH:]
    
    try:
        # Формируем сообщения с историей
        messages = [{"role": "system", "content": _system_prompt}]
        messages.extend(_chat_history[user_id])
        
        response = await _ai_client.chat.completions.create(
            model=_config.aitunnel_model_name,
            messages=messages,
            max_tokens=2000,
            temperature=0.7,
        )
        
        if response.choices and response.choices[0].message.content:
            assistant_response = response.choices[0].message.content.strip()
            
            # Добавляем ответ бота в историю
            _chat_history[user_id].append({"role": "assistant", "content": assistant_response})
            
            return assistant_response
        
        return "Извините, не удалось получить ответ. Попробуйте ещё раз!"
        
    except Exception as e:
        logger.error(f"Ошибка AI: {e}")
        return "Извините, сервис временно недоступен. Попробуйте позже! 🙏"


async def handle_message(event: dict):
    """Обрабатывает входящее сообщение — только в личных сообщениях"""
    user_id = event.get("user_id", "")
    message = event.get("message", "")
    channel_id = event.get("channel_id", "")
    channel_type = event.get("channel_type", "")
    sender_name = event.get("sender_name", "")
    
    # Отвечаем ТОЛЬКО в личных сообщениях (DM)
    is_dm = channel_type == "D"
    
    if not is_dm:
        # Игнорируем все сообщения из каналов
        return
    
    # Команда очистки истории
    if message.strip().lower() in ["/clear", "/reset", "очистить", "сброс"]:
        global _chat_history
        _chat_history[user_id] = []
        response_text = "🔄 История чата очищена! Начнём сначала."
    elif not message.strip():
        # Приветствие
        response_text = (
            "👋 Привет! Я **Гастро-Помощник**!\n\n"
            "Спроси меня о любом рецепте, и я с радостью помогу! 🍳\n\n"
            "Просто напиши название блюда, например: *борщ*, *карбонара*, *тирамису*\n\n"
            "💡 Напиши `/clear` чтобы очистить историю чата."
        )
    else:
        # Получаем ответ AI с учётом истории
        logger.info(f"Запрос от {sender_name}: {message[:50]}...")
        response_text = await get_ai_response(user_id, message)
    
    # Отправляем ответ
    success = await send_message(channel_id, response_text)
    if success:
        logger.info(f"Ответ отправлен в канал {channel_id}")
    else:
        logger.error(f"Не удалось отправить ответ в канал {channel_id}")


async def start_websocket_bot():
    """Запускает WebSocket бота"""
    global _config, _ai_client, _bot_user_id, _system_prompt
    
    # Загружаем конфигурацию
    _config = AppConfig()
    
    if not _config.mattermost_url or not _config.mattermost_bot_token:
        logger.warning("MATTERMOST_URL или MATTERMOST_BOT_TOKEN не настроены, WebSocket бот отключён")
        return
    
    # Инициализируем AI клиент
    _ai_client = AsyncOpenAI(
        api_key=_config.aitunnel_api_key,
        base_url=_config.aitunnel_base_url,
    )
    
    # Загружаем промпт
    _system_prompt = _load_system_prompt(_config.mattermost_prompt_file)
    
    # Получаем ID бота
    _bot_user_id = await get_bot_user_id(_config.mattermost_url, _config.mattermost_bot_token)
    logger.info(f"Bot User ID: {_bot_user_id}")
    
    # Создаём и запускаем WebSocket клиент
    ws_client = MattermostWebSocketClient(
        mattermost_url=_config.mattermost_url,
        bot_token=_config.mattermost_bot_token,
        bot_user_id=_bot_user_id,
        on_message=handle_message,
    )
    
    # Запускаем (бесконечный цикл с реконнектом)
    await ws_client.connect()
