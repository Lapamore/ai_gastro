from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid

class DiaryEntry(BaseModel):
    id: str = Field(alias="_id", default=None)
    name: str
    calories: int
    protein: float = 0
    fat: float = 0
    carbs: float = 0
    meal_type: str = "snack"
    timestamp: datetime
    
    class Config:
        populate_by_name = True
        
    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        # Для MongoDB используем _id
        if 'by_alias' in kwargs and kwargs['by_alias']:
            if 'id' in data:
                data['_id'] = data.pop('id')
        return data