"""
WebSocket бот для Mattermost.
Слушает все сообщения и отвечает в личных сообщениях.
История чата сохраняется в MySQL.
"""
import os
import json
import asyncio
import logging
import httpx
import pymysql
from typing import Optional, Dict, List

from openai import AsyncOpenAI

from src.infrastructure.impl.mattermost.MattermostWebSocket import MattermostWebSocketClient
from src.infrastructure.dependencies.Config import AppConfig

logger = logging.getLogger(__name__)

# Глобальные переменные
_config: Optional[AppConfig] = None
_ai_client: Optional[AsyncOpenAI] = None
_bot_user_id: Optional[str] = None
_system_prompt: str = ""
_mysql_connection = None

# Максимальное количество сообщений для контекста AI (чтобы не превысить лимит токенов)
MAX_CONTEXT_MESSAGES = 50


def _get_mysql_connection():
    """Получает или создаёт подключение к MySQL"""
    global _mysql_connection
    
    if _mysql_connection is None or not _mysql_connection.open:
        try:
            _mysql_connection = pymysql.connect(
                host=_config.mysql_host,
                port=_config.mysql_port,
                user=_config.mysql_user,
                password=_config.mysql_password,
                database=_config.mysql_database,
                autocommit=True,
                charset='utf8mb4'
            )
            logger.info("MySQL подключение для чата создано")
        except Exception as e:
            logger.error(f"Ошибка подключения к MySQL: {e}")
            return None
    
    return _mysql_connection


def save_message_to_db(user_id: str, role: str, content: str):
    """Сохраняет сообщение в MySQL"""
    conn = _get_mysql_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO mattermost_chat_history (user_id, role, content) VALUES (%s, %s, %s)",
            (user_id, role, content)
        )
        cursor.close()
    except Exception as e:
        logger.error(f"Ошибка сохранения сообщения в БД: {e}")

def save_user_allergies(user_id: str, allergy_list: List[str]):
    """Сохраняет аллергии или удаляет их, если пользователь написал 'нет'"""
    conn = _get_mysql_connection()
    if not conn: return False
    
    try:
        cursor = conn.cursor()
        
        # Проверяем, не хочет ли пользователь сбросить аллергии
        # (если список пуст или первое слово "нет", "очистить", "none")
        stop_words = ["нет", "очистить", "none", "no", "ничего", "empty"]
        if not allergy_list or (len(allergy_list) == 1 and allergy_list[0].lower() in stop_words):
            cursor.execute("DELETE FROM mattermost_allergies WHERE user_id = %s", (user_id,))
            logger.info(f"Аллергии пользователя {user_id} полностью удалены.")
            return "deleted"
        
        # Иначе сохраняем как обычно
        allergies_json = json.dumps(allergy_list, ensure_ascii=False)
        sql = """
            INSERT INTO mattermost_allergies (user_id, allergies) 
            VALUES (%s, %s) 
            ON DUPLICATE KEY UPDATE allergies = VALUES(allergies)
        """
        cursor.execute(sql, (user_id, allergies_json))
        return "saved"
    except Exception as e:
        logger.error(f"Ошибка БД: {e}")
        return False

def get_user_allergies(user_id: str) -> List[str]:
    """Загружает список аллергий пользователя из MySQL"""
    conn = _get_mysql_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT allergies FROM mattermost_allergies WHERE user_id = %s",
            (user_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        
        if row and row[0]:
            # Если данные в БД хранятся как JSON-строка, декодируем её
            allergies = row[0]
            if isinstance(allergies, str):
                return json.loads(allergies)
            return allergies # Если драйвер сам сконвертировал в список
        return []
    except Exception as e:
        logger.error(f"Ошибка загрузки аллергий из БД: {e}")
        return []

def get_chat_history_from_db(user_id: str, limit: int = MAX_CONTEXT_MESSAGES) -> List[dict]:
    """Загружает историю чата из MySQL"""
    conn = _get_mysql_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT role, content FROM mattermost_chat_history 
               WHERE user_id = %s 
               ORDER BY created_at DESC 
               LIMIT %s""",
            (user_id, limit)
        )
        rows = cursor.fetchall()
        cursor.close()
        
        # Переворачиваем чтобы старые были первыми
        history = [{"role": row[0], "content": row[1]} for row in reversed(rows)]
        return history
    except Exception as e:
        logger.error(f"Ошибка загрузки истории из БД: {e}")
        return []


def clear_chat_history_in_db(user_id: str):
    """Очищает историю чата в MySQL"""
    conn = _get_mysql_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM mattermost_chat_history WHERE user_id = %s", (user_id,))
        cursor.close()
        logger.info(f"История чата пользователя {user_id} очищена")
    except Exception as e:
        logger.error(f"Ошибка очистки истории в БД: {e}")


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

def delete_user_allergies(user_id: str):
    """Полностью удаляет данные об аллергиях пользователя из БД"""
    conn = _get_mysql_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM mattermost_allergies WHERE user_id = %s", (user_id,))
        cursor.close()
        logger.info(f"Данные об аллергиях пользователя {user_id} удалены.")
    except Exception as e:
        logger.error(f"Ошибка при удалении аллергий пользователя {user_id}: {e}")
        
async def get_ai_response(user_id: str, user_message: str) -> str:
    """Получает ответ от AI с учётом истории чата и аллергий"""
    
    # Сохраняем сообщение пользователя
    save_message_to_db(user_id, "user", user_message)
    
    # 1. Загружаем аллергии
    user_allergies = get_user_allergies(user_id)
    
    # 2. Формируем специальную вставку про аллергии
    allergy_context = ""
    if user_allergies:
        allergy_context = f"\n\nВНИМАНИЕ: У пользователя аллергия на следующие продукты: {', '.join(user_allergies)}. " \
                          f"КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО предлагать рецепты, содержащие эти ингредиенты!"

    # Загружаем историю из БД
    chat_history = get_chat_history_from_db(user_id, MAX_CONTEXT_MESSAGES)
    
    try:
        # 3. Формируем сообщения. 
        # Добавляем аллергии к системному промпту, чтобы AI всегда о них помнил.
        current_system_prompt = _system_prompt + allergy_context
        
        messages = [{"role": "system", "content": current_system_prompt}]
        messages.extend(chat_history)
        
        response = await _ai_client.chat.completions.create(
            model=_config.aitunnel_model_name,
            messages=messages,
            max_tokens=2000,
            temperature=0.7,
        )
        
        if response.choices and response.choices[0].message.content:
            assistant_response = response.choices[0].message.content.strip()
            save_message_to_db(user_id, "assistant", assistant_response)
            return assistant_response
        
        return "Извините, не удалось получить ответ."
        
    except Exception as e:
        logger.error(f"Ошибка AI: {e}")
        return "Извините, сервис временно недоступен. 🙏"


async def handle_message(event: dict):
    """Обрабатывает входящее сообщение"""
    user_id = event.get("user_id", "")
    message = event.get("message", "").strip()
    channel_id = event.get("channel_id", "")
    channel_type = event.get("channel_type", "")
    
    # Отвечаем ТОЛЬКО в личных сообщениях
    if channel_type != "D":
        return

    # --- НОВАЯ ЛОГИКА ДЛЯ АЛЛЕРГИЙ ---
    if message.lower().startswith("/allergies"):
            raw_list = message[len("/allergies"):].strip()
            allergy_items = [item.strip() for item in raw_list.split(",") if item.strip()]
            
            result = save_user_allergies(user_id, allergy_items)
            
            if result == "deleted":
                response_text = "🗑️ Ваши аллергии удалены из базы. Теперь я буду предлагать любые рецепты!"
            elif result == "saved":
                response_text = f"✅ Запомнил! Ваши аллергии: **{', '.join(allergy_items)}**."
            else:
                response_text = "❌ Ошибка при сохранении."
            
            await send_message(channel_id, response_text)
            return
    # --------------------------------

    # Команда очистки истории
    if message.lower() in ["/clear", "/reset", "очистить", "сброс"]:
        clear_chat_history_in_db(user_id)
        delete_user_allergies(user_id)
        response_text = "🔄 **Всё очищено!**\nИстория чата и ваши данные об аллергиях удалены. Теперь я снова буду предлагать любые рецепты. Начнём сначала! 😊"

    elif not message:
        response_text = (
            "👋 Привет! Я **Гастро-Помощник**!\n\n"
            "Спроси меня о любом рецепте! 🍳\n\n"
            "💡 Чтобы я не предлагал опасные продукты, напиши свои аллергии вот так:\n"
            "`/allergies орехи, мед, молоко`"
        )
    else:
        # Обычный запрос к AI
        response_text = await get_ai_response(user_id, message)
    
    await send_message(channel_id, response_text)

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
