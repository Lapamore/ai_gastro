from abc import ABC, abstractmethod
from typing import List, Optional
from ..models import ChatMessage, SessionMetadata

class AbstractDBService(ABC):
    # Методы для сообщений (остаются)
    @abstractmethod
    async def save_message(self, session_id: str, message: ChatMessage) -> None:
        pass

    @abstractmethod
    async def save_messages(self, session_id: str, messages: List[ChatMessage]) -> None:
        pass
    
    @abstractmethod
    async def get_history(self, session_id: str, limit: int = 20) -> List[ChatMessage]:
        pass

    # Новые методы для метаданных сессий
    @abstractmethod
    async def get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        pass

    @abstractmethod
    async def create_or_update_session_metadata(self, session_metadata: SessionMetadata) -> SessionMetadata:
        pass
    
    @abstractmethod
    async def list_sessions_metadata(self, user_id: Optional[str] = None, limit: int = 50, skip: int = 0) -> List[SessionMetadata]:
        # user_id пока опционален, в будущем для мульти-пользовательской системы
        pass
    
    # @abstractmethod # Опционально
    # async def delete_session_and_history(self, session_id: str) -> bool:
    #     pass