from abc import ABC, abstractmethod
from typing import List, Optional

from src.core.models.chatting.ChatMessageModel import ChatMessage
from src.core.models.sessions.SessionMetadataModel import SessionMetadata
from src.core.models.diary.DiaryEntryModel import DiaryEntry
from src.core.models.users.UserModel import User
from src.core.models.users.UserPreferencesModel import UserPreferences
from src.core.models.recipes.SavedRecipeModel import SavedRecipe


class AbstractDBService(ABC):
    
    # ==================== ПОЛЬЗОВАТЕЛИ ====================
    
    @abstractmethod
    async def get_or_create_user(self, user_id: str) -> User:
        """Получить пользователя или создать нового"""
        raise NotImplementedError()

    @abstractmethod
    async def get_or_create_user_by_yandex(
        self, yandex_id: str, display_name: str, email: str, avatar_id: str
    ) -> User:
        """Получить или создать пользователя по Yandex ID"""
        raise NotImplementedError()

    # ==================== ПРЕДПОЧТЕНИЯ ====================
    
    @abstractmethod
    async def get_user_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Получить предпочтения пользователя"""
        raise NotImplementedError()

    @abstractmethod
    async def save_user_preferences(self, preferences: UserPreferences) -> UserPreferences:
        """Сохранить/обновить предпочтения пользователя"""
        raise NotImplementedError()

    # ==================== СООБЩЕНИЯ ЧАТА ====================

    @abstractmethod
    async def save_message(self, session_id: str, message: ChatMessage) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def save_messages(self, session_id: str, messages: List[ChatMessage]) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def get_history(self, session_id: str, limit: int = 20) -> List[ChatMessage]:
        raise NotImplementedError()

    # ==================== СЕССИИ ====================

    @abstractmethod
    async def get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        raise NotImplementedError()

    @abstractmethod
    async def create_or_update_session_metadata(
        self, session_metadata: SessionMetadata, user_id: str
    ) -> SessionMetadata:
        raise NotImplementedError()

    @abstractmethod
    async def list_sessions_metadata(
        self, user_id: str, limit: int = 50, skip: int = 0
    ) -> List[SessionMetadata]:
        raise NotImplementedError()

    @abstractmethod
    async def delete_session_and_history(self, session_id: str) -> bool:
        raise NotImplementedError()

    # ==================== ДНЕВНИК КАЛОРИЙ ====================
        
    @abstractmethod
    async def add_diary_entry(self, user_id: str, entry: DiaryEntry) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def get_daily_summary(self, user_id: str) -> dict:
        raise NotImplementedError()

    @abstractmethod
    async def get_today_diary_entries(self, user_id: str) -> List[DiaryEntry]:
        """Получить записи дневника за сегодня"""
        raise NotImplementedError()
        
    @abstractmethod
    async def delete_diary_entry_by_name(self, user_id: str, name: str) -> bool:
        """Удалить запись из дневника за сегодня по названию"""
        raise NotImplementedError()

    # ==================== СОХРАНЁННЫЕ РЕЦЕПТЫ ====================

    @abstractmethod
    async def save_recipe(self, user_id: str, message_text: str, rating: str) -> SavedRecipe:
        """Сохранить рецепт (liked/disliked)"""
        raise NotImplementedError()

    @abstractmethod
    async def get_favorite_recipes(self, user_id: str) -> List[SavedRecipe]:
        """Получить любимые рецепты (rating='liked')"""
        raise NotImplementedError()

    @abstractmethod
    async def delete_saved_recipe(self, recipe_id: int, user_id: str) -> bool:
        """Удалить сохранённый рецепт"""
        raise NotImplementedError()
    
    # ==================== УПРАВЛЕНИЕ СОЕДИНЕНИЕМ ====================
    
    @abstractmethod
    async def close_connection(self):
        raise NotImplementedError()