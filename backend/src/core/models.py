# src/core/models.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

class ChatMessage(BaseModel):
    sender: str 
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SessionMetadata(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_id: Optional[str] = None
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda dt: dt.isoformat()}

# --- Модель для предпочтений пользователя ---
class UserPreferencesData(BaseModel):
    allergies: List[str] = Field(default_factory=list)
    dietary_restrictions: List[str] = Field(default_factory=list, alias="dietaryRestrictions")
    favorite_cuisines: List[str] = Field(default_factory=list, alias="favoriteCuisines")
    disliked_cuisines: List[str] = Field(default_factory=list, alias="dislikedCuisines")
    favorite_ingredients: List[str] = Field(default_factory=list, alias="favoriteIngredients")
    disliked_ingredients: List[str] = Field(default_factory=list, alias="dislikedIngredients")
    preferred_difficulty: Optional[str] = Field(default=None, alias="preferredDifficulty")
    available_time: Optional[str] = Field(default=None, alias="availableTime")

    class Config:
        populate_by_name = True # Для корректной работы с camelCase alias с фронтенда


class UserChatRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    preferences: Optional[UserPreferencesData] = None # <--- ДОБАВЛЕНО

class AIProviderResponse(BaseModel):
    reply: str

class APIChatResponse(BaseModel):
    reply: str
    session_id: str

class SessionMetadataListResponse(BaseModel):
    id: str
    title: str
    updated_at: datetime


class PersonalizedSuggestionsRequest(BaseModel):
    session_id: Optional[str] = None # Чтобы загрузить историю для этого пользователя/сессии
    preferences: Optional[UserPreferencesData] = None # Текущие настройки пользователя

class PersonalizedSuggestionsResponse(BaseModel):
    suggestions: List[str] # Список текстовых предложений
    # Можно добавить более структурированные предложения, например, [{title: "Паста", reason: "Вы любите итальянское"}, ...]