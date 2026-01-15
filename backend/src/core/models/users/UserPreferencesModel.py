from typing import List, Optional, Literal
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
    
    # Физические параметры пользователя
    weight: Optional[float] = None  # вес в кг
    height: Optional[float] = None  # рост в см
    age: Optional[int] = None  # возраст
    gender: Optional[Literal['male', 'female']] = None  # пол
    activity_level: Optional[Literal['sedentary', 'light', 'moderate', 'active', 'very_active']] = None
    goal: Optional[Literal['lose', 'maintain', 'gain']] = None  # цель
    
    # Расчётные значения БЖУ
    target_protein: Optional[float] = None  # граммы
    target_fat: Optional[float] = None  # граммы
    target_carbs: Optional[float] = None  # граммы

    class Config:
        from_attributes = True
    
    def calculate_tdee_and_macros(self) -> dict:
        """
        Рассчитывает TDEE (суточный расход калорий) по формуле Миффлина-Сан Жеора
        и рекомендуемые БЖУ на основе цели пользователя
        """
        if not all([self.weight, self.height, self.age, self.gender]):
            return None
        
        # Базовый метаболизм (BMR) по формуле Миффлина-Сан Жеора
        if self.gender == 'male':
            bmr = 10 * self.weight + 6.25 * self.height - 5 * self.age + 5
        else:
            bmr = 10 * self.weight + 6.25 * self.height - 5 * self.age - 161
        
        # Коэффициенты активности
        activity_multipliers = {
            'sedentary': 1.2,      # Сидячий образ жизни
            'light': 1.375,        # Лёгкая активность (1-3 раза/неделю)
            'moderate': 1.55,      # Умеренная активность (3-5 раз/неделю)
            'active': 1.725,       # Высокая активность (6-7 раз/неделю)
            'very_active': 1.9     # Очень высокая (спортсмены)
        }
        
        multiplier = activity_multipliers.get(self.activity_level, 1.55)
        tdee = bmr * multiplier
        
        # Корректировка калорий по цели
        goal_adjustments = {
            'lose': -500,      # Дефицит для похудения
            'maintain': 0,     # Поддержание веса
            'gain': 300        # Профицит для набора массы
        }
        
        calorie_adjustment = goal_adjustments.get(self.goal, 0)
        target_calories = max(1200, int(tdee + calorie_adjustment))  # Минимум 1200 ккал
        
        # Расчёт БЖУ в зависимости от цели
        if self.goal == 'lose':
            # Больше белка для сохранения мышц при похудении
            protein_ratio = 0.30  # 30% калорий из белка
            fat_ratio = 0.30      # 30% из жиров
            carb_ratio = 0.40     # 40% из углеводов
        elif self.goal == 'gain':
            # Больше углеводов для набора массы
            protein_ratio = 0.25
            fat_ratio = 0.25
            carb_ratio = 0.50
        else:  # maintain
            protein_ratio = 0.25
            fat_ratio = 0.30
            carb_ratio = 0.45
        
        # Калории в граммы: белок=4ккал/г, жиры=9ккал/г, углеводы=4ккал/г
        target_protein = round((target_calories * protein_ratio) / 4, 1)
        target_fat = round((target_calories * fat_ratio) / 9, 1)
        target_carbs = round((target_calories * carb_ratio) / 4, 1)
        
        return {
            'bmr': round(bmr),
            'tdee': round(tdee),
            'target_calories': target_calories,
            'target_protein': target_protein,
            'target_fat': target_fat,
            'target_carbs': target_carbs
        }
    
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
            weight=row.get("weight"),
            height=row.get("height"),
            age=row.get("age"),
            gender=row.get("gender"),
            activity_level=row.get("activity_level"),
            goal=row.get("goal"),
            target_protein=row.get("target_protein"),
            target_fat=row.get("target_fat"),
            target_carbs=row.get("target_carbs"),
        )
