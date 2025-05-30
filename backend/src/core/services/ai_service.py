from abc import ABC, abstractmethod
from typing import List, Optional # Добавим Optional
from ..models import ChatMessage, AIProviderResponse, UserPreferencesData

class AbstractAIService(ABC):
    @abstractmethod
    async def get_ai_response(
        self,
        user_prompt: str,
        conversation_history: List[ChatMessage],
        system_prompt: str, # Основной системный промпт (загруженный из файла)
        preferences_text: Optional[str] = None # <--- Текст с предпочтениями пользователя
    ) -> AIProviderResponse:
        """
        Получает ответ от AI модели.
        """
        pass

    @abstractmethod
    async def load_system_prompt(self, file_path: str) -> str:
        """
        Загружает системный промпт из файла.
        (Может быть не нужен, если грузим в __init__ реализации)
        """
        pass
    
    @abstractmethod
    async def get_personalized_suggestions(
        self,
        conversation_history: List[ChatMessage], # История предыдущих диалогов
        preferences: Optional[UserPreferencesData], # Явные предпочтения пользователя
        system_prompt: str # Базовый системный промпт
    ) -> List[str]: # Возвращает список текстовых предложений
        pass