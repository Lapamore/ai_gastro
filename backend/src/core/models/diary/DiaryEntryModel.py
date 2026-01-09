from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid

class DiaryEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_id: Optional[str] = None
    name: str
    calories: int
    protein: float = 0.0
    fat: float = 0.0
    carbs: float = 0.0
    meal_type: str = "snack"  # breakfast, lunch, dinner, snack
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True