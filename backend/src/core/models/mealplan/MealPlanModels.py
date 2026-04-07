from typing import Optional, List
from pydantic import BaseModel, Field


class FoodItem(BaseModel):
    """Продукт/блюдо в базе данных с нутриентами на 100г"""
    id: Optional[int] = None
    name: str
    calories: float          # ккал на 100г
    protein: float           # белки г/100г
    fat: float               # жиры г/100г
    carbs: float             # углеводы г/100г
    category: str            # breakfast, lunch, dinner, snack, universal
    tags: List[str] = Field(default_factory=list)  # теги: вегетарианское, острое, etc.
    allergens: List[str] = Field(default_factory=list)  # содержащиеся аллергены
    min_portion: float = 50.0    # минимальная порция (г)
    max_portion: float = 500.0   # максимальная порция (г)

    class Config:
        from_attributes = True

    @classmethod
    def from_db_row(cls, row: dict) -> "FoodItem":
        import json
        def parse_json_list(value) -> list:
            if value is None:
                return []
            if isinstance(value, list):
                return value
            try:
                return json.loads(value)
            except Exception:
                return []
        
        return cls(
            id=row.get("id"),
            name=row.get("name", ""),
            calories=row.get("calories", 0),
            protein=row.get("protein", 0),
            fat=row.get("fat", 0),
            carbs=row.get("carbs", 0),
            category=row.get("category", "universal"),
            tags=parse_json_list(row.get("tags")),
            allergens=parse_json_list(row.get("allergens")),
            min_portion=row.get("min_portion", 50.0),
            max_portion=row.get("max_portion", 500.0),
        )


class MealPlanItem(BaseModel):
    """Один элемент рассчитанного плана питания"""
    food_item: FoodItem
    portion_grams: float  # граммы
    meal_type: str        # breakfast / lunch / dinner / snack
    calories: float       # итого ккал для этой порции
    protein: float
    fat: float
    carbs: float


class MealPlanResult(BaseModel):
    """Полный результат оптимизации плана питания"""
    meals: List[MealPlanItem]
    total_calories: float
    total_protein: float
    total_fat: float
    total_carbs: float
    target_calories: float       # цель именно для построенного плана
    target_protein: float
    target_fat: float
    target_carbs: float
    daily_target_calories: float
    daily_target_protein: float
    daily_target_fat: float
    daily_target_carbs: float
    already_eaten_calories: float
    already_eaten_protein: float
    already_eaten_fat: float
    already_eaten_carbs: float
    deviation_calories: float   # |факт - цель|
    deviation_protein: float
    deviation_fat: float
    deviation_carbs: float
    solver_status: str          # optimal, infeasible, etc.
    solution_method: str
