from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid

class DiaryEntry(BaseModel):
    id: Optional[str] = Field(default=None)
    name: str
    calories: int
    protein: float = 0
    fat: float = 0
    carbs: float = 0
    meal_type: str = "snack"
    timestamp: datetime
    
    class Config:
        populate_by_name = True