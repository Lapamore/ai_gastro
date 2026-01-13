import logging
import uuid
import re
import json
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from datetime import datetime, timezone

from src.infrastructure.interfaces.IDataBase import AbstractDBService
from src.infrastructure.interfaces.IService import AbstractAIService
from src.infrastructure.impl.youtube.YoutubeService import YouTubeService
from src.core.models.chatting.APIChatResponseModel import APIChatResponse
from src.core.models.chatting.ChatMessageModel import ChatMessage
from src.core.models.chatting.UserChatRequestModel import UserChatRequest
from src.core.models.personalize.PersonalizedSuggestionsRequestModel import (
    PersonalizedSuggestionsRequest,
)
from src.core.models.personalize.PersonalizedSuggestionsResponseModel import (
    PersonalizedSuggestionsResponse,
)
from src.core.models.sessions.SessionMetadataListResponseModel import (
    SessionMetadataListResponse,
)
from src.core.models.sessions.SessionMetadataModel import SessionMetadata
from src.core.models.youtube.VideoSearchResultModel import VideoSearchResult
from src.core.models.diary.DiaryEntryModel import DiaryEntry
from src.infrastructure.dependencies.Dependencies import (
    get_ai_service_dependency,
    get_db_service_dependency,
    get_youtube_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Chat & Sessions"])


def generate_session_title(prompt: str) -> str:
    words = prompt.split()
    return " ".join(words[:5]) + ("..." if len(words) > 5 else "")


def build_diary_context(entries: List[DiaryEntry], daily_summary: dict) -> str:
    """Формирует контекст дневника для ИИ с информацией только за сегодня"""
    today_str = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    
    if not entries:
        return f"\n--- АКТУАЛЬНОЕ СОСТОЯНИЕ ДНЕВНИКА ПИТАНИЯ ({today_str}) ---\n⚠️ ВАЖНО: Сейчас в дневнике НЕТ ни одной записи о еде. Дневник пуст.\n--- КОНЕЦ АКТУАЛЬНЫХ ДАННЫХ ---\n"
    
    lines = [f"\n--- АКТУАЛЬНОЕ СОСТОЯНИЕ ДНЕВНИКА ПИТАНИЯ ({today_str}) ---"]
    lines.append(f"⚠️ ВАЖНО: Это ТЕКУЩИЙ список всей еды в дневнике. Если ранее упоминалось что-то, чего здесь нет - значит оно было удалено.")
    for entry in entries:
        time_str = entry.timestamp.strftime("%H:%M")
        lines.append(f"• {time_str} - {entry.name}: {entry.calories} ккал (Б:{entry.protein}г, Ж:{entry.fat}г, У:{entry.carbs}г)")
    
    lines.append(f"\nИТОГО ЗА СЕГОДНЯ: {daily_summary['totalCalories']} ккал "
                 f"(Б:{daily_summary['protein']}г, Ж:{daily_summary['fat']}г, У:{daily_summary['carbs']}г)")
    lines.append("--- КОНЕЦ АКТУАЛЬНЫХ ДАННЫХ ---\n")
    
    return "\n".join(lines)


class APIChatResponseWithVideos(APIChatResponse):
    videos: Optional[List[VideoSearchResult]] = None
    diary_updated: Optional[dict] = None  # Новое поле для обновлённых данных дневника


async def process_food_tags(bot_message_text: str, db_service: AbstractDBService) -> tuple[str, bool]:
    """Обрабатывает теги ADD_FOOD и DELETE_FOOD, возвращает очищенный текст и флаг изменения дневника"""
    
    diary_changed = False
    
    logger.info(f"Обработка тегов в ответе ИИ: {bot_message_text[:200]}...")
    
    # Обработка добавления еды
    add_food_pattern = r'\[ADD_FOOD:\s*(\{.*?\})\]'
    add_matches = re.findall(add_food_pattern, bot_message_text, re.DOTALL)
    logger.info(f"Найдено ADD_FOOD тегов: {len(add_matches)}")
    for match in add_matches:
        try:
            food_data = json.loads(match)
            entry = DiaryEntry(**food_data)
            await db_service.add_diary_entry(entry)
            logger.info(f"Автоматически добавлена еда: {entry.name}")
            diary_changed = True
        except Exception as e:
            logger.error(f"Ошибка парсинга ADD_FOOD: {e}, данные: {match}")
    
    # Обработка удаления еды
    delete_food_pattern = r'\[DELETE_FOOD:\s*["\']([^"\']+)["\']\]'
    delete_matches = re.findall(delete_food_pattern, bot_message_text)
    logger.info(f"Найдено DELETE_FOOD тегов: {len(delete_matches)}, значения: {delete_matches}")
    for food_name in delete_matches:
        try:
            logger.info(f"Попытка удаления еды: '{food_name}'")
            deleted = await db_service.delete_diary_entry_by_name(food_name)
            logger.info(f"Удаление еды '{food_name}': {'успешно' if deleted else 'не найдено'}")
            if deleted:
                diary_changed = True
        except Exception as e:
            logger.error(f"Ошибка удаления еды: {e}")
    
    # Убираем теги из текста ответа
    clean_text = re.sub(add_food_pattern, '', bot_message_text)
    clean_text = re.sub(r'\[DELETE_FOOD:\s*["\'][^"\']+["\']\]', '', clean_text)
    return clean_text.strip(), diary_changed


@router.post("/chat", response_model=APIChatResponseWithVideos)
async def handle_chat_request(
    chat_request: UserChatRequest,
    ai_service: AbstractAIService = Depends(get_ai_service_dependency),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
    youtube_service: YouTubeService = Depends(get_youtube_service),
):
    if not chat_request.prompt:
        raise HTTPException(
            status_code=400, detail="Сообщение пользователя (prompt) обязательно."
        )

    is_new_session = False
    if chat_request.session_id:
        current_session_id = chat_request.session_id
        session_meta = await db_service.get_session_metadata(current_session_id)
        if not session_meta:
            title = generate_session_title(chat_request.prompt)
            new_meta = SessionMetadata(id=current_session_id, title=title)
            session_meta = await db_service.create_or_update_session_metadata(new_meta)
    else:
        current_session_id = str(uuid.uuid4())
        is_new_session = True
        title = generate_session_title(chat_request.prompt)
        session_meta = SessionMetadata(id=current_session_id, title=title)
        session_meta = await db_service.create_or_update_session_metadata(session_meta)

    conversation_history_from_db: List[ChatMessage] = await db_service.get_history(
        current_session_id, limit=10
    )
    user_message = ChatMessage(sender="user", text=chat_request.prompt)

    # Получаем данные дневника за СЕГОДНЯ
    today_entries = await db_service.get_today_diary_entries()
    daily_summary = await db_service.get_daily_summary()
    diary_context = build_diary_context(today_entries, daily_summary)

    # Добавляем текущую дату в контекст
    current_date_context = f"Сегодняшняя дата: {datetime.now(timezone.utc).strftime('%d.%m.%Y')}.\n"

    preferences_prompt_text = current_date_context + diary_context
    if chat_request.preferences:
        prefs = chat_request.preferences
        pref_parts = []
        if prefs.allergies:
            pref_parts.append(f"- Аллергии: {', '.join(prefs.allergies)}.")
        if prefs.dietary_restrictions:
            pref_parts.append(
                f"- Диетические ограничения: {', '.join(prefs.dietary_restrictions)}."
            )
        if prefs.favorite_cuisines:
            pref_parts.append(f"- Любимые кухни: {', '.join(prefs.favorite_cuisines)}.")
        if prefs.disliked_cuisines:
            pref_parts.append(
                f"- Нелюбимые кухни: {', '.join(prefs.disliked_cuisines)}."
            )
        if prefs.favorite_ingredients:
            pref_parts.append(
                f"- Любимые ингредиенты: {', '.join(prefs.favorite_ingredients)}."
            )
        if prefs.disliked_ingredients:
            pref_parts.append(
                f"- Нелюбимые ингредиенты: {', '.join(prefs.disliked_ingredients)}."
            )
        if prefs.preferred_difficulty:
            pref_parts.append(f"- Сложность: {prefs.preferred_difficulty}.")
        if prefs.available_time:
            pref_parts.append(f"- Время на готовку: {prefs.available_time}.")
        if pref_parts:
            preferences_prompt_text += "\nУчти мои предпочтения:\n" + "\n".join(pref_parts)

    try:
        ai_provider_response = await ai_service.get_ai_response(
            user_prompt=user_message.text,
            conversation_history=conversation_history_from_db,
            system_prompt="",
            preferences_text=preferences_prompt_text,
        )

        if "Извините" in ai_provider_response.reply:
            raise HTTPException(status_code=503, detail=ai_provider_response.reply)

        bot_message_text = ai_provider_response.reply
        
        # Обрабатываем теги еды (добавление/удаление) и очищаем текст
        bot_message_text, diary_changed = await process_food_tags(bot_message_text, db_service)
        
        # Если дневник изменился, получаем обновлённые данные
        diary_updated = None
        if diary_changed:
            daily_summary = await db_service.get_daily_summary()
            today_entries = await db_service.get_today_diary_entries()
            diary_updated = {
                "summary": daily_summary,
                "entries": [entry.model_dump() for entry in today_entries]
            }
        
        found_videos: Optional[List[VideoSearchResult]] = None

        if ai_provider_response.trigger_video_search_query:
            logger.info(
                f"AI запросил поиск видео: '{ai_provider_response.trigger_video_search_query}'"
            )
            videos_from_yt = await youtube_service.search_videos(
                query=ai_provider_response.trigger_video_search_query, max_results=2
            )
            if videos_from_yt:
                found_videos = videos_from_yt

        bot_message = ChatMessage(sender="assistant", text=bot_message_text)
        await db_service.save_messages(current_session_id, [user_message, bot_message])

        if session_meta:
            session_meta.updated_at = datetime.now(timezone.utc)
            await db_service.create_or_update_session_metadata(session_meta)

        return APIChatResponseWithVideos(
            reply=bot_message.text, 
            session_id=current_session_id, 
            videos=found_videos,
            diary_updated=diary_updated
        )

    except HTTPException:
        raise
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail="Сервис БД недоступен.")
    except Exception as e:
        logger.error(f"Ошибка в chat_router ({current_session_id}): {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}"
        )


@router.get("/sessions", response_model=List[SessionMetadataListResponse])
async def list_user_sessions(
    db_service: AbstractDBService = Depends(get_db_service_dependency),
    limit: int = 50,
    skip: int = 0,
):
    sessions_metadata = await db_service.list_sessions_metadata(limit=limit, skip=skip)
    return [
        SessionMetadataListResponse(**meta.model_dump()) for meta in sessions_metadata
    ]


@router.get("/sessions/{session_id}/history", response_model=List[ChatMessage])
async def get_session_history_route(
    session_id: str,
    db_service: AbstractDBService = Depends(get_db_service_dependency),
    limit: int = 100,
):
    history = await db_service.get_history(session_id, limit=limit)
    if not history and not await db_service.get_session_metadata(session_id):
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    return history


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session_route(
    session_id: str, db_service: AbstractDBService = Depends(get_db_service_dependency)
):
    if not await db_service.get_session_metadata(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена"
        )
    if not await db_service.delete_session_and_history(session_id):
        raise HTTPException(status_code=500, detail="Не удалось удалить сессию")
    return


@router.post(
    "/suggestions", response_model=PersonalizedSuggestionsResponse, tags=["Suggestions"]
)
async def get_personalized_suggestions_route(
    request_data: PersonalizedSuggestionsRequest,
    ai_service: AbstractAIService = Depends(get_ai_service_dependency),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    history = (
        await db_service.get_history(request_data.session_id, limit=50)
        if request_data.session_id
        else []
    )
    suggestions = await ai_service.get_personalized_suggestions(
        conversation_history=history,
        preferences=request_data.preferences,
        system_prompt="",
    )
    return PersonalizedSuggestionsResponse(suggestions=suggestions)
# Эндпоинт для сохранения новой еды
@router.post("/diary/entries")
async def add_food_entry(
    entry: DiaryEntry, 
    db_service: AbstractDBService = Depends(get_db_service_dependency)
):
    await db_service.add_diary_entry(entry)
    return {"status": "success"}

# Эндпоинт для получения сводки за сегодня (вызывается фронтендом при F5)
@router.get("/diary/daily-summary")
async def get_daily_summary_route(
    db_service: AbstractDBService = Depends(get_db_service_dependency)
):
    return await db_service.get_daily_summary()

# Эндпоинт для удаления еды по названию
@router.delete("/diary/entries/{food_name}")
async def delete_food_entry(
    food_name: str,
    db_service: AbstractDBService = Depends(get_db_service_dependency)
):
    deleted = await db_service.delete_diary_entry_by_name(food_name)
    if deleted:
        return {"status": "success", "message": f"Запись '{food_name}' удалена"}
    raise HTTPException(status_code=404, detail=f"Запись '{food_name}' не найдена за сегодня")