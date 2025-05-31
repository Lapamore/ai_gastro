from typing import Optional
from pydantic import BaseModel

from src.core.models.settings.UserPreferencesDataModel import (
    UserPreferencesData,
)


class PersonalizedSuggestionsRequest(BaseModel):
    session_id: Optional[str] = (
        None  
    )
    preferences: Optional[UserPreferencesData] = None  
