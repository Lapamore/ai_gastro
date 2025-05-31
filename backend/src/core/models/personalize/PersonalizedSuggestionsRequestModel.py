from typing import Optional
from pydantic import BaseModel

from src.core.models.settings.UserPreferencesDataModel import (
    UserPreferencesData,
)


class PersonalizedSuggestionsRequest(BaseModel):
    session_id: Optional[str] = (
        None  # Чтобы загрузить историю для этого пользователя/сессии
    )
    preferences: Optional[UserPreferencesData] = None  # Текущие настройки пользователя
