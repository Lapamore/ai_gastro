"""
Сервис для интеграции с Mattermost ботом.
Предоставляет функционал:
- Получение рецептов через AI
- Хранение аллергий пользователей в MySQL
"""
import os
import json
import logging
import httpx
from typing import Optional, List, Dict
from datetime import datetime, timezone

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletion

from src.core.models.mattermost.MattermostModels import (
    MattermostBotResponse,
    MattermostUserAllergies,
)


logger = logging.getLogger(__name__)


class MattermostBotService:
    """Сервис для обработки запросов от Mattermost бота"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        webhook_token: str,
        mattermost_url: Optional[str] = None,
        bot_token: Optional[str] = None,
        system_prompt_file: Optional[str] = None,
        mysql_connection = None,
    ):
        """
        Инициализация сервиса Mattermost бота.
        
        Args:
            api_key: API ключ для AI сервиса
            base_url: Базовый URL для AI сервиса
            model_name: Название модели AI
            webhook_token: Токен для верификации webhook запросов
            mattermost_url: URL Mattermost сервера (опционально, для отправки сообщений)
            bot_token: Токен бота Mattermost (опционально, для API)
            system_prompt_file: Путь к файлу с системным промптом
            mysql_connection: Соединение с MySQL (опционально)
        """
        self.model_name = model_name
        self.webhook_token = webhook_token
        self.mattermost_url = mattermost_url
        self.bot_token = bot_token
        self.mysql_connection = mysql_connection
        
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        
        # Кэш аллергий (для быстрого доступа)
        self._user_allergies_cache: Dict[str, List[str]] = {}
        
        # Загружаем системный промпт
        self.base_system_prompt = self._load_system_prompt(system_prompt_file)
        
        logger.info("MattermostBotService инициализирован")
    
    def _load_system_prompt(self, file_path: Optional[str]) -> str:
        """Загружает системный промпт из файла"""
        default_prompt = """Ты — Гастро-Помощник. Отвечай только на вопросы о рецептах.
Если у пользователя есть аллергии — учитывай их при подборе рецептов."""
        
        if not file_path or not os.path.exists(file_path):
            logger.warning(f"Файл промпта не найден: {file_path}, используем fallback")
            return default_prompt
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Ошибка загрузки промпта: {e}")
            return default_prompt
    
    def verify_webhook_token(self, token: str) -> bool:
        """Проверяет токен webhook запроса"""
        return token == self.webhook_token
    
    def get_user_allergies(self, user_id: str) -> List[str]:
        """Получает список аллергий пользователя из MySQL"""
        # Проверяем кэш
        if user_id in self._user_allergies_cache:
            return self._user_allergies_cache[user_id]
        
        # Загружаем из БД
        if self.mysql_connection:
            try:
                cursor = self.mysql_connection.cursor()
                cursor.execute(
                    "SELECT allergies FROM mattermost_allergies WHERE user_id = %s",
                    (user_id,)
                )
                result = cursor.fetchone()
                cursor.close()
                
                if result:
                    allergies = json.loads(result[0]) if isinstance(result[0], str) else result[0]
                    self._user_allergies_cache[user_id] = allergies
                    return allergies
            except Exception as e:
                logger.error(f"Ошибка получения аллергий из БД: {e}")
        
        return []
    
    def set_user_allergies(self, user_id: str, allergies: List[str]) -> MattermostUserAllergies:
        """
        Устанавливает список аллергий для пользователя и сохраняет в MySQL.
        
        Args:
            user_id: ID пользователя Mattermost
            allergies: Список аллергий
            
        Returns:
            Обновлённый объект аллергий
        """
        cleaned_allergies = [a.strip().lower() for a in allergies if a.strip()]
        
        # Сохраняем в MySQL
        print(f"DEBUG: mysql_connection = {self.mysql_connection}")
        if self.mysql_connection:
            try:
                cursor = self.mysql_connection.cursor()
                cursor.execute(
                    """INSERT INTO mattermost_allergies (user_id, allergies) 
                       VALUES (%s, %s) 
                       ON DUPLICATE KEY UPDATE allergies = %s""",
                    (user_id, json.dumps(cleaned_allergies), json.dumps(cleaned_allergies))
                )
                self.mysql_connection.commit()
                cursor.close()
                print(f"DEBUG: Saved to DB: {user_id} -> {cleaned_allergies}")
                logger.info(f"Аллергии пользователя {user_id} сохранены в БД: {cleaned_allergies}")
            except Exception as e:
                print(f"DEBUG: DB Error: {e}")
                logger.error(f"Ошибка сохранения аллергий в БД: {e}")
        else:
            print("DEBUG: mysql_connection is None!")
        
        # Обновляем кэш
        self._user_allergies_cache[user_id] = cleaned_allergies
        
        user_allergies = MattermostUserAllergies(
            user_id=user_id,
            allergies=cleaned_allergies,
            updated_at=datetime.now(timezone.utc)
        )
        
        logger.info(f"Аллергии пользователя {user_id} обновлены: {cleaned_allergies}")
        return user_allergies
    
    def add_user_allergies(self, user_id: str, new_allergies: List[str]) -> MattermostUserAllergies:
        """Добавляет аллергии к существующему списку"""
        current = self.get_user_allergies(user_id)
        new_cleaned = [a.strip().lower() for a in new_allergies if a.strip()]
        combined = list(set(current + new_cleaned))
        return self.set_user_allergies(user_id, combined)
    
    def remove_user_allergies(self, user_id: str, allergies_to_remove: List[str]) -> MattermostUserAllergies:
        """Удаляет указанные аллергии из списка пользователя"""
        current = self.get_user_allergies(user_id)
        to_remove_lower = [a.strip().lower() for a in allergies_to_remove]
        updated = [a for a in current if a not in to_remove_lower]
        return self.set_user_allergies(user_id, updated)
    
    def clear_user_allergies(self, user_id: str) -> None:
        """Очищает все аллергии пользователя"""
        if self.mysql_connection:
            try:
                cursor = self.mysql_connection.cursor()
                cursor.execute("DELETE FROM mattermost_allergies WHERE user_id = %s", (user_id,))
                self.mysql_connection.commit()
                cursor.close()
            except Exception as e:
                logger.error(f"Ошибка удаления аллергий из БД: {e}")
        
        if user_id in self._user_allergies_cache:
            del self._user_allergies_cache[user_id]
        logger.info(f"Аллергии пользователя {user_id} очищены")
    
    def _build_system_prompt_with_allergies(self, user_id: str) -> str:
        """Формирует системный промпт с учётом аллергий пользователя"""
        allergies = self.get_user_allergies(user_id)
        
        if allergies:
            allergies_text = f"У пользователя аллергия на: {', '.join(allergies)}. ОБЯЗАТЕЛЬНО исключай эти продукты из рецептов!"
        else:
            allergies_text = "Аллергии не указаны."
        
        return self.base_system_prompt.replace("{allergies_context}", allergies_text)
    
    async def get_recipe_response(
        self,
        user_id: str,
        user_message: str,
        user_name: Optional[str] = None
    ) -> str:
        """
        Получает ответ AI на вопрос о рецептах.
        
        Args:
            user_id: ID пользователя Mattermost
            user_message: Сообщение пользователя
            user_name: Имя пользователя (опционально)
            
        Returns:
            Текст ответа от AI
        """
        system_prompt = self._build_system_prompt_with_allergies(user_id)
        
        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        logger.info(f"Запрос от пользователя {user_name or user_id}: {user_message[:100]}...")
        
        try:
            chat_completion: ChatCompletion = await self.async_client.chat.completions.create(
                messages=messages,
                model=self.model_name,
                max_tokens=2000,
                temperature=0.7,
            )
            
            if chat_completion.choices and chat_completion.choices[0].message.content:
                response = chat_completion.choices[0].message.content.strip()
                logger.info(f"Ответ AI для {user_id}: {response[:100]}...")
                return response
            
            return "Извините, не удалось получить ответ. Попробуйте ещё раз!"
            
        except Exception as e:
            logger.error(f"Ошибка при получении ответа AI: {e}", exc_info=True)
            return "Извините, сервис временно недоступен. Попробуйте позже! 🙏"
    
    def format_allergies_response(self, user_id: str, action: str) -> MattermostBotResponse:
        """
        Форматирует ответ об аллергиях.
        
        Args:
            user_id: ID пользователя
            action: Тип действия (list, set, add, remove, clear)
            
        Returns:
            Ответ для Mattermost
        """
        allergies = self.get_user_allergies(user_id)
        
        if action == "list":
            if allergies:
                text = f"🚫 **Ваши аллергии:**\n• " + "\n• ".join(allergies)
            else:
                text = "✅ У вас не указано никаких аллергий.\n\nЧтобы добавить, используйте:\n`/allergies орехи, молоко, глютен`"
        elif action == "clear":
            text = "✅ Список аллергий очищен!"
        else:
            if allergies:
                text = f"✅ Аллергии обновлены!\n\n🚫 **Текущий список:**\n• " + "\n• ".join(allergies)
            else:
                text = "✅ Список аллергий пуст."
        
        return MattermostBotResponse(
            text=text,
            response_type="ephemeral"  # Видно только пользователю
        )
    
    async def process_message(
        self,
        user_id: str,
        text: str,
        user_name: Optional[str] = None,
        trigger_word: Optional[str] = None
    ) -> MattermostBotResponse:
        """
        Обрабатывает входящее сообщение от пользователя.
        
        Args:
            user_id: ID пользователя
            text: Текст сообщения
            user_name: Имя пользователя
            trigger_word: Триггерное слово (если есть)
            
        Returns:
            Ответ бота для Mattermost
        """
        # Убираем trigger word из текста если есть
        clean_text = text
        if trigger_word and text.lower().startswith(trigger_word.lower()):
            clean_text = text[len(trigger_word):].strip()
        
        if not clean_text:
            return MattermostBotResponse(
                text="👋 Привет! Я **Гастро-Помощник**!\n\n"
                     "Спроси меня о любом рецепте, и я с радостью помогу! 🍳\n\n"
                     "**Команды:**\n"
                     "• `gastro /allergies орехи, молоко` — указать аллергии\n"
                     "• `gastro /allergies` — посмотреть свои аллергии\n"
                     "• `gastro /allergies clear` — очистить аллергии\n"
                     "• `gastro [блюдо]` — получить рецепт",
                response_type="in_channel"
            )
        
        # Обработка команды /allergies
        if clean_text.startswith("/allergies"):
            allergy_text = clean_text[len("/allergies"):].strip()
            
            if not allergy_text:
                # Показать текущие аллергии
                return self.format_allergies_response(user_id, "list")
            elif allergy_text.lower() == "clear":
                # Очистить аллергии
                self.clear_user_allergies(user_id)
                return self.format_allergies_response(user_id, "clear")
            else:
                # Установить аллергии
                allergies = [a.strip() for a in allergy_text.replace(",", " ").split() if a.strip()]
                self.set_user_allergies(user_id, allergies)
                return self.format_allergies_response(user_id, "set")
        
        # Получаем ответ от AI
        ai_response = await self.get_recipe_response(user_id, clean_text, user_name)
        
        return MattermostBotResponse(
            text=ai_response,
            response_type="in_channel"
        )
    
    async def send_message_to_channel(
        self,
        channel_id: str,
        message: str
    ) -> bool:
        """
        Отправляет сообщение в канал Mattermost (требует bot_token и mattermost_url).
        
        Args:
            channel_id: ID канала
            message: Текст сообщения
            
        Returns:
            True если успешно
        """
        if not self.mattermost_url or not self.bot_token:
            logger.warning("Mattermost URL или bot token не настроены")
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.mattermost_url}/api/v4/posts",
                    headers={
                        "Authorization": f"Bearer {self.bot_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "channel_id": channel_id,
                        "message": message
                    }
                )
                return response.status_code == 201
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в Mattermost: {e}")
            return False
