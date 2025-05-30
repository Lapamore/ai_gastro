from abc import ABC, abstractmethod
from typing import List
from ..models import ChatMessage, AIProviderResponse

class AbstractAIService(ABC):
    @abstractmethod
    async def get_ai_response(
        self,
        user_prompt: str,
        conversation_history: List[ChatMessage],
        system_prompt: str,
    ) -> AIProviderResponse:
        """
        Получает ответ от AI модели на основе промпта пользователя и истории диалога.
        """
        raise NotImplementedError()

    @abstractmethod
    async def load_system_prompt(self, file_path: str) -> str:
        """
        Загружает системный промпт из файла.
        """
        raise NotImplementedError()