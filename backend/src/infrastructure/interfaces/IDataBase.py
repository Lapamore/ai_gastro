from abc import ABC, abstractmethod
from typing import List, Optional

from src.core.models.chatting.ChatMessageModel import ChatMessage
from src.core.models.sessions.SessionMetadataModel import SessionMetadata
from src.core.models.diary.DiaryEntryModel import DiaryEntry

class AbstractDBService(ABC):
    @abstractmethod
    async def save_message(self, session_id: str, message: ChatMessage) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def save_messages(self, session_id: str, messages: List[ChatMessage]) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def get_history(self, session_id: str, limit: int = 20) -> List[ChatMessage]:
        raise NotImplementedError()

    @abstractmethod
    async def get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        raise NotImplementedError()

    @abstractmethod
    async def create_or_update_session_metadata(
        self, session_metadata: SessionMetadata
    ) -> SessionMetadata:
        raise NotImplementedError()

    @abstractmethod
    async def list_sessions_metadata(
        self, user_id: Optional[str] = None, limit: int = 50, skip: int = 0
    ) -> List[SessionMetadata]:
        raise NotImplementedError()

    @abstractmethod
    async def delete_session_and_history(self, session_id: str) -> bool:
        raise NotImplementedError()
        
    @abstractmethod
    async def add_diary_entry(self, entry: DiaryEntry) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def get_daily_summary(self) -> dict:
        raise NotImplementedError()

    @abstractmethod
    async def get_today_diary_entries(self) -> List[DiaryEntry]:
        """Получить записи дневника за сегодня"""
        raise NotImplementedError()
        
    @abstractmethod
    async def delete_diary_entry_by_name(self, name: str) -> bool:
        """Удалить запись из дневника за сегодня по названию"""
        raise NotImplementedError()