from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
import logging

from src.infrastructure.interfaces.IDataBase import AbstractDBService
from src.infrastructure.dependencies.Dependencies import get_db_service_dependency
from src.api.auth_dependency import get_current_user_id
from src.services.meal_optimizer import optimize_meal_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mealplan", tags=["Meal Plan"])


class MealPlanRequest(BaseModel):
    """Запрос на генерацию плана питания"""
    consider_diary: bool = True  # учитывать уже съеденное


class MealItemResponse(BaseModel):
    name: str
    portion_grams: float
    meal_type: str
    calories: float
    protein: float
    fat: float
    carbs: float
    category: str


class MealPlanResponse(BaseModel):
    meals: List[MealItemResponse]
    total_calories: float
    total_protein: float
    total_fat: float
    total_carbs: float
    target_calories: float
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
    deviation_calories: float
    deviation_protein: float
    deviation_fat: float
    deviation_carbs: float
    solver_status: str
    solution_method: str


@router.post("/generate", response_model=MealPlanResponse)
async def generate_meal_plan(
    request: MealPlanRequest,
    user_id: str = Depends(get_current_user_id),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    """
    Генерирует план питания на день, используя оптимизационную модель
    с учётом БЖУ, ограничений и пользовательских предпочтений.
    
    Учитывает:
    - Целевые калории и БЖУ пользователя (из профиля)
    - Уже съеденную пищу за сегодня (из дневника)
    - Аллергены и ограничения пользователя
    """
    # 1. Получаем предпочтения пользователя
    prefs = await db_service.get_user_preferences(user_id)
    
    target_cal = 2000.0
    target_prot = 125.0
    target_fat = 67.0
    target_carbs = 225.0
    excluded_allergens = []
    excluded_ingredients = []
    favorite_ingredients = []
    favorite_cuisines = []
    disliked_cuisines = []
    dietary_restrictions = []
    
    if prefs:
        target_cal = float(prefs.target_calories or 2000)
        target_prot = float(prefs.target_protein or 125)
        target_fat = float(prefs.target_fat or 67)
        target_carbs = float(prefs.target_carbs or 225)
        excluded_allergens = prefs.allergies or []
        excluded_ingredients = prefs.disliked_ingredients or []
        favorite_ingredients = prefs.favorite_ingredients or []
        favorite_cuisines = prefs.favorite_cuisines or []
        disliked_cuisines = prefs.disliked_cuisines or []
        dietary_restrictions = prefs.dietary_restrictions or []
    
    # 2. Получаем дневник за сегодня
    eaten_cal = 0.0
    eaten_prot = 0.0
    eaten_fat = 0.0
    eaten_carbs = 0.0
    
    if request.consider_diary:
        daily_summary = await db_service.get_daily_summary(user_id)
        eaten_cal = float(daily_summary.get("totalCalories", 0))
        eaten_prot = float(daily_summary.get("protein", 0))
        eaten_fat = float(daily_summary.get("fat", 0))
        eaten_carbs = float(daily_summary.get("carbs", 0))
    
    # 3. Получаем продукты из БД
    food_items = await db_service.get_all_food_items()
    
    if not food_items:
        raise HTTPException(status_code=404, detail="Нет доступных продуктов для планирования")
    
    # 4. Запускаем оптимизатор
    logger.info(
        f"Запуск mealplan-оптимизатора: цель={target_cal}ккал, "
        f"уже съедено={eaten_cal}ккал, продуктов={len(food_items)}"
    )
    
    result = optimize_meal_plan(
        food_items=food_items,
        target_calories=target_cal,
        target_protein=target_prot,
        target_fat=target_fat,
        target_carbs=target_carbs,
        excluded_allergens=excluded_allergens,
        excluded_ingredients=excluded_ingredients,
        favorite_ingredients=favorite_ingredients,
        favorite_cuisines=favorite_cuisines,
        disliked_cuisines=disliked_cuisines,
        dietary_restrictions=dietary_restrictions,
        already_eaten_calories=eaten_cal,
        already_eaten_protein=eaten_prot,
        already_eaten_fat=eaten_fat,
        already_eaten_carbs=eaten_carbs,
    )
    
    logger.info(f"Mealplan-результат: статус={result.solver_status}, блюд={len(result.meals)}")
    
    return MealPlanResponse(
        meals=[
            MealItemResponse(
                name=m.food_item.name,
                portion_grams=m.portion_grams,
                meal_type=m.meal_type,
                calories=m.calories,
                protein=m.protein,
                fat=m.fat,
                carbs=m.carbs,
                category=m.food_item.category,
            )
            for m in result.meals
        ],
        total_calories=result.total_calories,
        total_protein=result.total_protein,
        total_fat=result.total_fat,
        total_carbs=result.total_carbs,
        target_calories=result.target_calories,
        target_protein=result.target_protein,
        target_fat=result.target_fat,
        target_carbs=result.target_carbs,
        daily_target_calories=result.daily_target_calories,
        daily_target_protein=result.daily_target_protein,
        daily_target_fat=result.daily_target_fat,
        daily_target_carbs=result.daily_target_carbs,
        already_eaten_calories=result.already_eaten_calories,
        already_eaten_protein=result.already_eaten_protein,
        already_eaten_fat=result.already_eaten_fat,
        already_eaten_carbs=result.already_eaten_carbs,
        deviation_calories=result.deviation_calories,
        deviation_protein=result.deviation_protein,
        deviation_fat=result.deviation_fat,
        deviation_carbs=result.deviation_carbs,
        solver_status=result.solver_status,
        solution_method=result.solution_method,
    )
