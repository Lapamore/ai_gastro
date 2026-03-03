from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SavedRecipe(BaseModel):
    id: Optional[int] = None
    user_id: str
    message_text: str
    rating: str  # 'liked' or 'disliked'
    created_at: Optional[datetime] = None


class SaveRecipeRequest(BaseModel):
    message_text: str
    rating: str  # 'liked' or 'disliked'


class SavedRecipeResponse(BaseModel):
    id: int
    message_text: str
    rating: str
    created_at: datetime
