import os
import logging
import re
from typing import List, Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletion

from src.infrastructure.interfaces.IService import AbstractAIService
from src.core.models.chatting.ChatMessageModel import ChatMessage
from src.core.models.settings.UserPreferencesDataModel import UserPreferencesData
from src.core.models.youtube.AIProviderResponseModel import AIProviderResponse


logger = logging.getLogger(__name__)


class OpenAIAITunnelService(AbstractAIService):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        system_prompt_file: Optional[str] = None,
    ):
        if not api_key:
            logger.error(
                "API ключ для AITunnel не предоставлен при инициализации сервиса."
            )

        self.model_name = model_name
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.base_system_prompt = "Ты — полезный ИИ-ассистент."
        if system_prompt_file:
            try:
                with open(system_prompt_file, "r", encoding="utf-8") as f:
                    self.base_system_prompt = f.read().strip()
                logger.info(
                    f"Базовый системный промпт успешно загружен из {system_prompt_file}"
                )
            except Exception as e:
                logger.error(
                    f"Ошибка при загрузке системного промпта из {system_prompt_file}: {e}. Используется fallback."
                )

    async def load_system_prompt(self, file_path: str) -> str:
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception as e:
                logger.error(
                    f"Ошибка при динамической загрузке системного промпта из {file_path}: {e}"
                )
        return self.base_system_prompt

    def _convert_history_to_openai_format(
        self,
        effective_system_prompt: str,
        conversation_history: List[ChatMessage],
        user_prompt: str,
        realtime_context: Optional[str] = None,
    ) -> List[ChatCompletionMessageParam]:
        messages: List[ChatCompletionMessageParam] = []
        if effective_system_prompt:
            messages.append({"role": "system", "content": effective_system_prompt})
        for msg in conversation_history:
            role = "user" if msg.sender == "user" else "assistant"
            messages.append({"role": role, "content": msg.text})
        
        # Добавляем актуальные данные (дневник, профиль) ПРЯМО перед вопросом пользователя
        # Это гарантирует что AI увидит свежие данные последними
        final_user_content = user_prompt
        if realtime_context:
            final_user_content = f"🔴 АКТУАЛЬНЫЕ ДАННЫЕ (ИГНОРИРУЙ ВСЮ ИСТОРИЮ ЧАТА, ИСПОЛЬЗУЙ ТОЛЬКО ЭТО):\n{realtime_context}\n\n📝 МОЙ ВОПРОС: {user_prompt}"
        
        messages.append({"role": "user", "content": final_user_content})
        return messages

    async def get_ai_response(
        self,
        user_prompt: str,
        conversation_history: List[ChatMessage],
        system_prompt: Optional[str] = None,
        preferences_text: Optional[str] = None,
        realtime_context: Optional[str] = None,
    ) -> AIProviderResponse:

        effective_system_prompt = system_prompt or self.base_system_prompt

        if not effective_system_prompt.strip():
            logger.warning("Итоговый системный промпт пуст!")
            effective_system_prompt = "Ты полезный ассистент."

        openai_messages = self._convert_history_to_openai_format(
            effective_system_prompt, conversation_history, user_prompt, realtime_context
        )
        logger.info(
            f"Запрос к AITunnel API. Модель: {self.model_name}. Сообщений: {len(openai_messages)}"
        )

        try:
            chat_completion: ChatCompletion = (
                await self.async_client.chat.completions.create(
                    messages=openai_messages,
                    model=self.model_name,
                    max_tokens=4000,
                    temperature=0.6,
                )
            )

            ai_text_reply = ""
            if (
                chat_completion.choices
                and chat_completion.choices[0].message
                and chat_completion.choices[0].message.content
            ):
                ai_text_reply = chat_completion.choices[0].message.content.strip()

            video_search_query = None
            match = re.search(
                r"\[YOUTUBE_SEARCH:\s*\"(.*?)\"\s*\]", ai_text_reply, re.IGNORECASE
            )
            if match:
                video_search_query = match.group(1).strip()
                ai_text_reply = ai_text_reply.replace(match.group(0), "").strip()
                logger.info(
                    f"AI запросил поиск видео на YouTube: '{video_search_query}'"
                )
            else:
                logger.info("AI НЕ запросил поиск видео (тег не найден в ответе).")

            return AIProviderResponse(
                reply=ai_text_reply, trigger_video_search_query=video_search_query
            )

        except Exception as e:
            logger.error(
                f"Ошибка при взаимодействии с AITunnel (OpenAI SDK): {e}", exc_info=True
            )
            return AIProviderResponse(
                reply="Извините, сервис AI временно недоступен.",
                trigger_video_search_query=None,
            )

    async def get_personalized_suggestions(
        self,
        conversation_history: List[ChatMessage],
        preferences: Optional[UserPreferencesData],
        system_prompt: Optional[str] = None,
    ) -> List[str]:
        effective_system_prompt = system_prompt or self.base_system_prompt
        preferences_text_parts: List[str] = []
        if preferences:
            if preferences.allergies:
                preferences_text_parts.append(
                    f"- Аллергии: {', '.join(preferences.allergies)}."
                )
            if preferences.dietary_restrictions:
                preferences_text_parts.append(
                    f"- Диета: {', '.join(preferences.dietary_restrictions)}."
                )
            if preferences.favorite_cuisines:
                preferences_text_parts.append(
                    f"- Любимые кухни: {', '.join(preferences.favorite_cuisines)}."
                )

        preferences_text_for_prompt = ""
        if preferences_text_parts:
            preferences_text_for_prompt = "Мои предпочтения:\n" + "\n".join(
                preferences_text_parts
            )

        history_summary = (
            "Ранее мы обсуждали:\n"
            + "\n".join(
                [
                    f"{'Я' if m.sender=='user' else 'Ты'}: {m.text}"
                    for m in conversation_history[-6:]
                ]
            )
            if conversation_history
            else "Это наш первый диалог."
        )

        recommendation_prompt_content = f"""
        {history_summary}
        {preferences_text_for_prompt}

        Исходя из этой информации (моей истории и предпочтений), предложи мне 2-3 интересных и разнообразных идеи для еды или рецепта на сегодня. 
        Представь каждое предложение как отдельный пункт, кратко объяснив, почему оно может мне подойти.
        Например:
        1.  [Название блюда/идея] - потому что ты упоминал X, и это сочетается с Y.
        2.  [Название блюда/идея] - так как ты любишь кухню Z, это блюдо тебе понравится.
        """
        openai_messages: List[ChatCompletionMessageParam] = []
        if effective_system_prompt:
            openai_messages.append(
                {"role": "system", "content": effective_system_prompt}
            )
        openai_messages.append(
            {"role": "user", "content": recommendation_prompt_content}
        )

        try:
            chat_completion = await self.async_client.chat.completions.create(
                messages=openai_messages,
                model=self.model_name,
                max_tokens=500,
                temperature=0.8,
                n=1,
            )
            raw_reply = (
                chat_completion.choices[0].message.content.strip()
                if chat_completion.choices and chat_completion.choices[0].message
                else ""
            )
            suggestions = []
            if raw_reply:
                potential_suggestions = re.findall(
                    r"^\s*(\d+\.\s*.*?|- \s*.*?|\* \s*.*?)$", raw_reply, re.MULTILINE
                )
                if potential_suggestions:
                    suggestions = [s.strip() for s in potential_suggestions]
                else:
                    lines = [
                        line.strip() for line in raw_reply.split("\n") if line.strip()
                    ]
                    if len(lines) > 1:
                        suggestions = lines
                    elif raw_reply:
                        suggestions.append(raw_reply)

            return suggestions if suggestions else ["К сожалению, сейчас нет идей."]
        except Exception as e:
            logger.error(f"Ошибка персонализированных предложений: {e}", exc_info=True)
            return ["Ошибка получения предложений."]
