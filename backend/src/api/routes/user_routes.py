from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, Literal
from pydantic import BaseModel
from typing import List
import logging

from src.core.models.users.UserModel import User
from src.core.models.users.UserPreferencesModel import UserPreferences
from src.infrastructure.interfaces.IDataBase import AbstractDBService
from src.infrastructure.dependencies.Dependencies import get_db_service_dependency
from src.api.auth_dependency import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["User"])


class PreferencesInput(BaseModel):
    """Модель для входящих данных предпочтений (в camelCase как с фронта)"""
    allergies: List[str] = []
    dietaryRestrictions: List[str] = []
    favoriteCuisines: List[str] = []
    dislikedCuisines: List[str] = []
    favoriteIngredients: List[str] = []
    dislikedIngredients: List[str] = []
    preferredDifficulty: Optional[str] = None
    availableTime: Optional[int] = None
    targetCalories: int = 2000
    # Новые поля - физические параметры
    weight: Optional[float] = None
    height: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[Literal['male', 'female']] = None
    activityLevel: Optional[Literal['sedentary', 'light', 'moderate', 'active', 'very_active']] = None
    goal: Optional[Literal['lose', 'maintain', 'gain']] = None


class PreferencesResponse(BaseModel):
    """Модель для ответа предпочтений (в camelCase для фронта)"""
    allergies: List[str] = []
    dietaryRestrictions: List[str] = []
    favoriteCuisines: List[str] = []
    dislikedCuisines: List[str] = []
    favoriteIngredients: List[str] = []
    dislikedIngredients: List[str] = []
    preferredDifficulty: Optional[str] = None
    availableTime: Optional[int] = None
    targetCalories: int = 2000
    # Новые поля
    weight: Optional[float] = None
    height: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    activityLevel: Optional[str] = None
    goal: Optional[str] = None
    targetProtein: Optional[float] = None
    targetFat: Optional[float] = None
    targetCarbs: Optional[float] = None


@router.get("/me")
async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db_service: AbstractDBService = Depends(get_db_service_dependency)
):
    """Получить или создать пользователя"""
    user = await db_service.get_or_create_user(user_id)
    return {"id": user.id, "username": user.username, "created_at": user.created_at.isoformat()}


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    user_id: str = Depends(get_current_user_id),
    db_service: AbstractDBService = Depends(get_db_service_dependency)
):
    """Получить предпочтения пользователя"""
    prefs = await db_service.get_user_preferences(user_id)
    
    if prefs is None:
        return PreferencesResponse()
    
    return PreferencesResponse(
        allergies=prefs.allergies,
        dietaryRestrictions=prefs.dietary_restrictions,
        favoriteCuisines=prefs.favorite_cuisines,
        dislikedCuisines=prefs.disliked_cuisines,
        favoriteIngredients=prefs.favorite_ingredients,
        dislikedIngredients=prefs.disliked_ingredients,
        preferredDifficulty=prefs.preferred_difficulty,
        availableTime=prefs.available_time,
        targetCalories=prefs.target_calories,
        weight=prefs.weight,
        height=prefs.height,
        age=prefs.age,
        gender=prefs.gender,
        activityLevel=prefs.activity_level,
        goal=prefs.goal,
        targetProtein=prefs.target_protein,
        targetFat=prefs.target_fat,
        targetCarbs=prefs.target_carbs
    )


@router.post("/preferences", response_model=PreferencesResponse)
async def save_preferences(
    prefs_input: PreferencesInput,
    user_id: str = Depends(get_current_user_id),
    db_service: AbstractDBService = Depends(get_db_service_dependency)
):
    """Сохранить предпочтения пользователя"""
    logger.info(f"Сохранение предпочтений для пользователя {user_id}")
    
    prefs = UserPreferences(
        user_id=user_id,
        allergies=prefs_input.allergies,
        dietary_restrictions=prefs_input.dietaryRestrictions,
        favorite_cuisines=prefs_input.favoriteCuisines,
        disliked_cuisines=prefs_input.dislikedCuisines,
        favorite_ingredients=prefs_input.favoriteIngredients,
        disliked_ingredients=prefs_input.dislikedIngredients,
        preferred_difficulty=prefs_input.preferredDifficulty,
        available_time=prefs_input.availableTime,
        target_calories=prefs_input.targetCalories,
        weight=prefs_input.weight,
        height=prefs_input.height,
        age=prefs_input.age,
        gender=prefs_input.gender,
        activity_level=prefs_input.activityLevel,
        goal=prefs_input.goal
    )
    
    saved = await db_service.save_user_preferences(prefs)
    
    return PreferencesResponse(
        allergies=saved.allergies,
        dietaryRestrictions=saved.dietary_restrictions,
        favoriteCuisines=saved.favorite_cuisines,
        dislikedCuisines=saved.disliked_cuisines,
        favoriteIngredients=saved.favorite_ingredients,
        dislikedIngredients=saved.disliked_ingredients,
        preferredDifficulty=saved.preferred_difficulty,
        availableTime=saved.available_time,
        targetCalories=saved.target_calories,
        weight=saved.weight,
        height=saved.height,
        age=saved.age,
        gender=saved.gender,
        activityLevel=saved.activity_level,
        goal=saved.goal,
        targetProtein=saved.target_protein,
        targetFat=saved.target_fat,
        targetCarbs=saved.target_carbs
    )
