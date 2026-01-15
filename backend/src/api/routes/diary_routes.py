from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid
import logging

from src.core.models.diary.DiaryEntryModel import DiaryEntry
from src.infrastructure.interfaces.IDataBase import AbstractDBService
from src.infrastructure.dependencies.Dependencies import get_db_service_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diary", tags=["diary"])


class DiaryEntryInput(BaseModel):
    name: str
    calories: int
    protein: float = 0
    fat: float = 0
    carbs: float = 0
    mealType: str = "snack"


def get_user_id(x_user_id: str = Header(..., alias="X-User-ID")) -> str:
    """Получаем user_id из заголовка запроса"""
    return x_user_id


@router.get("/daily-summary")
async def get_daily_summary(
    user_id: str = Depends(get_user_id),
    db_service: AbstractDBService = Depends(get_db_service_dependency)
):
    """Получить суммарные данные калорий за сегодня"""
    return await db_service.get_daily_summary(user_id)


@router.get("/entries")
async def get_today_entries(
    user_id: str = Depends(get_user_id),
    db_service: AbstractDBService = Depends(get_db_service_dependency)
):
    """Получить все записи дневника за сегодня"""
    entries = await db_service.get_today_diary_entries(user_id)
    return [
        {
            "id": str(e.id) if e.id else str(uuid.uuid4()),
            "name": e.name,
            "calories": e.calories,
            "protein": e.protein,
            "fat": e.fat,
            "carbs": e.carbs,
            "mealType": e.meal_type,
            "timestamp": e.timestamp.isoformat()
        }
        for e in entries
    ]


@router.post("/add")
async def add_diary_entry(
    entry: DiaryEntryInput,
    user_id: str = Depends(get_user_id),
    db_service: AbstractDBService = Depends(get_db_service_dependency)
):
    """Добавить запись в дневник вручную"""
    logger.info(f"Добавление записи в дневник для пользователя {user_id}: {entry.name}")
    
    diary_entry = DiaryEntry(
        id=str(uuid.uuid4()),
        name=entry.name,
        calories=entry.calories,
        protein=entry.protein,
        fat=entry.fat,
        carbs=entry.carbs,
        meal_type=entry.mealType,
        timestamp=datetime.now(timezone.utc)
    )
    
    await db_service.add_diary_entry(user_id, diary_entry)
    
    summary = await db_service.get_daily_summary(user_id)
    return {"success": True, "summary": summary}


@router.delete("/delete/{name}")
async def delete_diary_entry(
    name: str,
    user_id: str = Depends(get_user_id),
    db_service: AbstractDBService = Depends(get_db_service_dependency)
):
    """Удалить запись из дневника по названию"""
    deleted = await db_service.delete_diary_entry_by_name(user_id, name)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    
    summary = await db_service.get_daily_summary(user_id)
    return {"success": True, "summary": summary}
