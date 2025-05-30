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
            raise ValueError("API ключ для AITunnel не предоставлен.")
        
        self.model_name = model_name
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.system_prompt_template = "Ты — полезный ИИ-ассистент." 
        if system_prompt_file:
            try:
                with open(system_prompt_file, 'r', encoding='utf-8') as f:
                    self.system_prompt_template = f.read()
                logger.info(f"Системный промпт успешно загружен из {system_prompt_file}")
            except FileNotFoundError:
                logger.error(f"Файл системного промпта не найден: {system_prompt_file}")
            except Exception as e:
                logger.error(f"Ошибка при загрузке системного промпта: {e}")

    async def load_system_prompt(self, file_path: str) -> str:
        try:
            if os.path.exists(file_path):
                 with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            logger.warning(f"Файл системного промпта не найден по пути (load_system_prompt): {file_path}")
        except Exception as e:
            logger.error(f"Ошибка при динамической загрузке системного промпта: {e}")
        return "Ты — полезный ИИ-ассистент."

    def _convert_history_to_openai_format(
        self,
        system_prompt: str,
        conversation_history: List[ChatMessage],
        user_prompt: str
    ) -> List[ChatCompletionMessageParam]:
        
        messages: List[ChatCompletionMessageParam] = []
        messages.append({"role": "system", "content": system_prompt})

        for msg in conversation_history:
            role = "user" if msg.sender == "user" else "assistant"
            messages.append({"role": role, "content": msg.text})
        
        messages.append({"role": "user", "content": user_prompt})
        return messages

    async def get_ai_response(
        self,
        user_prompt: str,
        conversation_history: List[ChatMessage],
        system_prompt: Optional[str] = None, 
    ) -> AIProviderResponse:
        
        current_system_prompt = system_prompt or self.system_prompt_template
        if not current_system_prompt:
            logger.warning("Системный промпт не был загружен, используется fallback.")
            current_system_prompt = "Ты — полезный ИИ-ассистент."

        openai_messages = self._convert_history_to_openai_format(
            current_system_prompt,
            conversation_history,
            user_prompt
        )

        logger.info(f"Запрос к AITunnel API. Модель: {self.model_name}. Кол-во сообщений: {len(openai_messages)}")

        try:
            chat_completion: ChatCompletion = await self.async_client.chat.completions.create(
                messages=openai_messages,
                model=self.model_name,
                max_tokens=4096,
                temperature=0.7, 
                stream=False, # Пока без стриминга
            )

            ai_reply = ""
            if chat_completion.choices and chat_completion.choices[0].message:
                ai_reply = chat_completion.choices[0].message.content or ""
            
            logger.info(f"Ответ от AITunnel API получен (длина: {len(ai_reply)}).")
            return AIProviderResponse(reply=ai_reply.strip())

        except Exception as e:
            logger.error(f"Ошибка при взаимодействии с AITunnel (OpenAI SDK): {e}", exc_info=True)
            return AIProviderResponse(reply="Извините, произошла ошибка при обращении к AI. Попробуйте позже.")