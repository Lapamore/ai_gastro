from typing import Optional, List
from pydantic import BaseModel, Field
from src.core.models.settings.UserPreferencesDataModel import (
    UserPreferencesData,
)


class GroupCookingSettings(BaseModel):
    guest_count: int = Field(default=2, alias="guestCount")
    allergies: List[str] = Field(default_factory=list)
    restrictions: List[str] = Field(default_factory=list)

    class Config:
        populate_by_name = True


class UserChatRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    preferences: Optional[UserPreferencesData] = None
    cooking_mode: Optional[str] = Field(default="solo", alias="cookingMode")
    group_settings: Optional[GroupCookingSettings] = Field(default=None, alias="groupSettings")

    class Config:
        populate_by_name = True
