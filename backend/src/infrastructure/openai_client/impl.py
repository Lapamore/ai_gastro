# src/infrastructure/openai_client/impl.py
import os
import logging
from typing import List, Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletion

from src.core.services.ai_service import AbstractAIService
from src.core.models import ChatMessage, AIProviderResponse

logger = logging.getLogger(__name__)

class OpenAIAITunnelService(AbstractAIService):
    def __init__(self, api_key: str, base_url: str, model_name: str, system_prompt_file: Optional[str] = None):
        if not api_key:
            # В реальном приложении лучше бросать ошибку или обрабатывать это на уровне конфигурации
            logger.error("API ключ для AITunnel не предоставлен при инициализации сервиса.")
            # raise ValueError("API ключ для AITunnel не предоставлен.")
        
        self.model_name = model_name
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.base_system_prompt = "Ты — полезный ИИ-ассистент." # Fallback, если файл не загружен
        if system_prompt_file:
            try:
                with open(system_prompt_file, 'r', encoding='utf-8') as f:
                    self.base_system_prompt = f.read().strip()
                logger.info(f"Базовый системный промпт успешно загружен из {system_prompt_file}")
            except FileNotFoundError:
                logger.error(f"Файл системного промпта не найден: {system_prompt_file}. Используется fallback.")
            except Exception as e:
                logger.error(f"Ошибка при загрузке системного промпта: {e}. Используется fallback.")
    
    async def load_system_prompt(self, file_path: str) -> str:
        # Этот метод может быть использован для перезагрузки или если __init__ не справился
        # Но в текущей схеме base_system_prompt устанавливается в __init__
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except Exception as e:
                logger.error(f"Ошибка при динамической загрузке системного промпта из {file_path}: {e}")
        return self.base_system_prompt # Возвращаем загруженный или fallback

    def _convert_history_to_openai_format(
        self,
        effective_system_prompt: str, # Итоговый системный промпт (с предпочтениями)
        conversation_history: List[ChatMessage],
        user_prompt: str
    ) -> List[ChatCompletionMessageParam]:
        
        messages: List[ChatCompletionMessageParam] = []
        if effective_system_prompt: # Добавляем системный промпт, только если он есть
            messages.append({"role": "system", "content": effective_system_prompt})

        for msg in conversation_history:
            role = "user" if msg.sender == "user" else "assistant"
            messages.append({"role": role, "content": msg.text})
        
        messages.append({"role": "user", "content": user_prompt})
        return messages

    async def get_ai_response(
        self,
        user_prompt: str,
        conversation_history: List[ChatMessage],
        system_prompt: Optional[str] = None, # Может быть передан для переопределения базового
        preferences_text: Optional[str] = None 
    ) -> AIProviderResponse:
        
        # Собираем итоговый системный промпт
        effective_system_prompt = system_prompt or self.base_system_prompt
        if preferences_text:
            effective_system_prompt = f"{effective_system_prompt}\n\n{preferences_text}"
        
        if not effective_system_prompt.strip(): # Проверка, что промпт не пустой после всех манипуляций
            logger.warning("Итоговый системный промпт пуст! AI может работать некорректно.")
            # Можно установить дефолтный, если совсем пусто
            # effective_system_prompt = "Ты полезный ассистент."


        openai_messages = self._convert_history_to_openai_format(
            effective_system_prompt,
            conversation_history,
            user_prompt
        )

        logger.info(f"Запрос к AITunnel API. Модель: {self.model_name}. Сообщений в запросе: {len(openai_messages)}")
        # logger.debug(f"Сообщения для OpenAI (первые 2): {openai_messages[:2]}") # Логируем часть для отладки

        try:
            chat_completion: ChatCompletion = await self.async_client.chat.completions.create(
                messages=openai_messages,
                model=self.model_name,
                max_tokens=4000, # Можно настроить в .env
                temperature=0.6, # Можно настроить
            )

            ai_reply = ""
            if chat_completion.choices and chat_completion.choices[0].message and chat_completion.choices[0].message.content:
                ai_reply = chat_completion.choices[0].message.content
            
            logger.info(f"Ответ от AITunnel API получен (длина: {len(ai_reply)}).")
            return AIProviderResponse(reply=ai_reply.strip())

        except Exception as e:
            logger.error(f"Ошибка при взаимодействии с AITunnel (OpenAI SDK): {e}", exc_info=True)
            return AIProviderResponse(reply="Извините, сервис AI временно недоступен. Попробуйте позже.")