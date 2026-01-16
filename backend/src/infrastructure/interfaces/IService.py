from abc import ABC, abstractmethod
from typing import List, Optional

from src.core.models.settings.UserPreferencesDataModel import UserPreferencesData
from src.core.models.youtube.AIProviderResponseModel import AIProviderResponse
from src.core.models.chatting.ChatMessageModel import ChatMessage


class AbstractAIService(ABC):
    @abstractmethod
    async def get_ai_response(
        self,
        user_prompt: str,
        conversation_history: List[ChatMessage],
        system_prompt: str,
        preferences_text: Optional[str] = None,
        realtime_context: Optional[str] = None,
    ) -> AIProviderResponse:
        """
        Получает ответ от AI модели, может содержать запрос на поиск видео.
        """
        pass

    @abstractmethod
    async def load_system_prompt(self, file_path: str) -> str:
        pass

    @abstractmethod
    async def get_personalized_suggestions(
        self,
        conversation_history: List[ChatMessage],
        preferences: Optional[UserPreferencesData],
        system_prompt: str,
    ) -> List[str]:
        pass
