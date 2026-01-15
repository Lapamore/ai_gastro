from typing import List, Optional
from pydantic import BaseModel, Field


class UserPreferences(BaseModel):
    id: Optional[int] = None
    user_id: str
    
    # Аллергии и ограничения
    allergies: List[str] = Field(default_factory=list)
    dietary_restrictions: List[str] = Field(default_factory=list)
    
    # Предпочтения по кухням
    favorite_cuisines: List[str] = Field(default_factory=list)
    disliked_cuisines: List[str] = Field(default_factory=list)
    
    # Предпочтения по ингредиентам
    favorite_ingredients: List[str] = Field(default_factory=list)
    disliked_ingredients: List[str] = Field(default_factory=list)
    
    # Другие настройки
    preferred_difficulty: Optional[str] = None  # easy, medium, hard
    available_time: Optional[int] = None  # в минутах
    target_calories: int = 2000

    class Config:
        from_attributes = True
    
    def lists_to_json(self) -> dict:
        """Конвертирует списки в JSON для хранения в БД"""
        import json
        return {
            "allergies": json.dumps(self.allergies, ensure_ascii=False),
            "dietary_restrictions": json.dumps(self.dietary_restrictions, ensure_ascii=False),
            "favorite_cuisines": json.dumps(self.favorite_cuisines, ensure_ascii=False),
            "disliked_cuisines": json.dumps(self.disliked_cuisines, ensure_ascii=False),
            "favorite_ingredients": json.dumps(self.favorite_ingredients, ensure_ascii=False),
            "disliked_ingredients": json.dumps(self.disliked_ingredients, ensure_ascii=False),
        }
    
    @classmethod
    def from_db_row(cls, row: dict) -> "UserPreferences":
        """Создаёт объект из строки БД, парся JSON поля"""
        import json
        
        def parse_json_list(value) -> List[str]:
            if value is None:
                return []
            if isinstance(value, list):
                return value
            try:
                return json.loads(value)
            except:
                return []
        
        return cls(
            id=row.get("id"),
            user_id=row.get("user_id"),
            allergies=parse_json_list(row.get("allergies")),
            dietary_restrictions=parse_json_list(row.get("dietary_restrictions")),
            favorite_cuisines=parse_json_list(row.get("favorite_cuisines")),
            disliked_cuisines=parse_json_list(row.get("disliked_cuisines")),
            favorite_ingredients=parse_json_list(row.get("favorite_ingredients")),
            disliked_ingredients=parse_json_list(row.get("disliked_ingredients")),
            preferred_difficulty=row.get("preferred_difficulty"),
            available_time=row.get("available_time"),
            target_calories=row.get("target_calories", 2000),
        )
