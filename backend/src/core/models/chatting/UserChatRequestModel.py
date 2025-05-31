from typing import Optional
from pydantic import BaseModel
from src.core.models.settings.UserPreferencesDataModel import (
    UserPreferencesData,
)


class UserChatRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    preferences: Optional[UserPreferencesData] = None
