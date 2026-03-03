import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import List

from src.infrastructure.interfaces.IDataBase import AbstractDBService
from src.infrastructure.dependencies.Dependencies import get_db_service_dependency
from src.api.auth_dependency import get_current_user_id
from src.core.models.recipes.SavedRecipeModel import (
    SaveRecipeRequest,
    SavedRecipeResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Recipes"])


@router.post("/recipes", response_model=SavedRecipeResponse)
async def save_recipe(
    req: SaveRecipeRequest,
    user_id: str = Depends(get_current_user_id),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    """Сохранить рецепт (liked/disliked)"""
    if req.rating not in ("liked", "disliked"):
        raise HTTPException(status_code=400, detail="rating должен быть 'liked' или 'disliked'")

    recipe = await db_service.save_recipe(
        user_id=user_id,
        message_text=req.message_text,
        rating=req.rating,
    )
    return SavedRecipeResponse(
        id=recipe.id,
        message_text=recipe.message_text,
        rating=recipe.rating,
        created_at=recipe.created_at,
    )


@router.get("/recipes/favorites", response_model=List[SavedRecipeResponse])
async def get_favorite_recipes(
    user_id: str = Depends(get_current_user_id),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    """Получить список любимых рецептов"""
    recipes = await db_service.get_favorite_recipes(user_id)
    return [
        SavedRecipeResponse(
            id=r.id,
            message_text=r.message_text,
            rating=r.rating,
            created_at=r.created_at,
        )
        for r in recipes
    ]


@router.delete("/recipes/{recipe_id}", status_code=204)
async def delete_recipe(
    recipe_id: int,
    user_id: str = Depends(get_current_user_id),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    """Удалить сохранённый рецепт"""
    deleted = await db_service.delete_saved_recipe(recipe_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Рецепт не найден")
    return
