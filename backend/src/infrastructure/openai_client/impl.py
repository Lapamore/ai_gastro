# src/infrastructure/openai_client/impl.py
import os
import logging
from typing import List, Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletion

from src.core.services.ai_service import AbstractAIService
from src.core.models import ChatMessage, AIProviderResponse, UserPreferencesData

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
        
    async def get_personalized_suggestions(
        self,
        conversation_history: List[ChatMessage],
        preferences: Optional[UserPreferencesData],
        system_prompt: Optional[str] = None, # Базовый системный промпт
    ) -> List[str]:
        
        effective_system_prompt = system_prompt or self.base_system_prompt
        
        preferences_text = ""
        if preferences:
            pref_parts = []
            if preferences.allergies: pref_parts.append(f"- Аллергии: {', '.join(preferences.allergies)}.")
            if preferences.dietary_restrictions: pref_parts.append(f"- Диета: {', '.join(preferences.dietary_restrictions)}.")
            if preferences.favorite_cuisines: pref_parts.append(f"- Любимые кухни: {', '.join(preferences.favorite_cuisines)}.")
            # ... можно добавить и другие предпочтения ...
            if pref_parts:
                preferences_text = "Вот мои текущие предпочтения и ограничения:\n" + "\n".join(pref_parts)

        # Формируем промпт для AI с просьбой дать рекомендации
        # Важно: история здесь - это общая история пользователя, а не текущего диалога (хотя может совпадать)
        history_summary_for_prompt = "Ранее мы обсуждали:\n"
        if conversation_history:
            # Возьмем последние несколько обменов для краткости, или можно сделать саммари
            for msg in conversation_history[-6:]: # Последние 3 обмена
                role = "Я (пользователь)" if msg.sender == "user" else "Ты (помощник)"
                history_summary_for_prompt += f"{role}: {msg.text}\n"
        else:
            history_summary_for_prompt = "У нас пока не было диалогов.\n"

        recommendation_prompt = f"""
        {history_summary_for_prompt}
        {preferences_text}

        Исходя из этой информации (моей истории и предпочтений), предложи мне 2-3 интересных и разнообразных идеи для еды или рецепта на сегодня. 
        Представь каждое предложение как отдельный пункт, кратко объяснив, почему оно может мне подойти.
        Например:
        1.  [Название блюда/идея] - потому что ты упоминал X, и это сочетается с Y.
        2.  [Название блюда/идея] - так как ты любишь кухню Z, это блюдо тебе понравится.
        """
        
        openai_messages: List[ChatCompletionMessageParam] = []
        if effective_system_prompt:
             openai_messages.append({"role": "system", "content": effective_system_prompt})
        openai_messages.append({"role": "user", "content": recommendation_prompt})


        logger.info(f"Запрос персонализированных предложений к AITunnel. Модель: {self.model_name}.")
        # logger.debug(f"Промпт для предложений: {recommendation_prompt}")

        try:
            chat_completion: ChatCompletion = await self.async_client.chat.completions.create(
                messages=openai_messages,
                model=self.model_name,
                max_tokens=500, # Для предложений не нужно очень много токенов
                temperature=0.8, # Чуть выше температура для креативности
                n=1, # Хотим один набор предложений
            )

            raw_reply = ""
            if chat_completion.choices and chat_completion.choices[0].message and chat_completion.choices[0].message.content:
                raw_reply = chat_completion.choices[0].message.content.strip()
            
            # AI может вернуть нумерованный список или просто текст. Пытаемся распарсить.
            # Простой парсинг по строкам, начинающимся с цифры или маркера списка.
            suggestions = []
            if raw_reply:
                lines = raw_reply.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and (line[0].isdigit() or line.startswith('- ') or line.startswith('* ')):
                        suggestions.append(line)
                if not suggestions and raw_reply: # Если не удалось распарсить как список, берем все как одно предложение
                    suggestions.append(raw_reply)

            logger.info(f"Получено {len(suggestions)} персонализированных предложений.")
            return suggestions if suggestions else ["К сожалению, сейчас не могу придумать ничего особенного. Может, просто спросишь, что хочешь?"]

        except Exception as e:
            logger.error(f"Ошибка при получении персонализированных предложений: {e}", exc_info=True)
            return ["Извините, не удалось получить персонализированные предложения сейчас."]