from abc import ABC, abstractmethod
from typing import List, Optional # Добавим Optional
from ..models import ChatMessage, AIProviderResponse

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