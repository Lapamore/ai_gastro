# src/services/api/chat_router.py
import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from datetime import datetime, timezone

from src.core.models import (
    UserChatRequest, APIChatResponse, ChatMessage, 
    SessionMetadata, SessionMetadataListResponse, UserPreferencesData,
    VideoSearchResult, # Импортируем VideoSearchResult
    PersonalizedSuggestionsRequest, PersonalizedSuggestionsResponse # Для другого эндпоинта
)
from src.core.services.ai_service import AbstractAIService
from src.core.services.database_service import AbstractDBService
from src.infrastructure.youtube_service import YouTubeService 
from src.infrastructure.dependencies import (
    get_ai_service_dependency, 
    get_db_service_dependency,
    get_youtube_service 
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Chat & Sessions"])

def generate_session_title(prompt: str) -> str:
    words = prompt.split()
    return " ".join(words[:5]) + ("..." if len(words) > 5 else "")

class APIChatResponseWithVideos(APIChatResponse): # Наследуемся или создаем новую
    videos: Optional[List[VideoSearchResult]] = None


@router.post("/chat", response_model=APIChatResponseWithVideos) 
async def handle_chat_request(
    chat_request: UserChatRequest,
    ai_service: AbstractAIService = Depends(get_ai_service_dependency),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
    youtube_service: YouTubeService = Depends(get_youtube_service), 
):
    if not chat_request.prompt:
        raise HTTPException(status_code=400, detail="Сообщение пользователя (prompt) обязательно.")

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
    
    conversation_history_from_db: List[ChatMessage] = await db_service.get_history(current_session_id, limit=10)
    user_message = ChatMessage(sender="user", text=chat_request.prompt)

    preferences_prompt_text = ""
    if chat_request.preferences:
        prefs = chat_request.preferences
        pref_parts = []
        if prefs.allergies: pref_parts.append(f"- Аллергии: {', '.join(prefs.allergies)}.")
        if prefs.dietary_restrictions: pref_parts.append(f"- Диетические ограничения: {', '.join(prefs.dietary_restrictions)}.")
        if prefs.favorite_cuisines: pref_parts.append(f"- Любимые кухни: {', '.join(prefs.favorite_cuisines)}.")
        if prefs.disliked_cuisines: pref_parts.append(f"- Нелюбимые кухни: {', '.join(prefs.disliked_cuisines)}.")
        if prefs.favorite_ingredients: pref_parts.append(f"- Любимые ингредиенты: {', '.join(prefs.favorite_ingredients)}.")
        if prefs.disliked_ingredients: pref_parts.append(f"- Нелюбимые ингредиенты: {', '.join(prefs.disliked_ingredients)}.")
        if prefs.preferred_difficulty: pref_parts.append(f"- Сложность: {prefs.preferred_difficulty}.")
        if prefs.available_time: pref_parts.append(f"- Время на готовку: {prefs.available_time}.")
        if pref_parts:
            preferences_prompt_text = "Учти мои предпочтения:\n" + "\n".join(pref_parts)

    try:
        ai_provider_response = await ai_service.get_ai_response(
            user_prompt=user_message.text,
            conversation_history=conversation_history_from_db,
            system_prompt="", 
            preferences_text=preferences_prompt_text
        )
        
        if "Извините" in ai_provider_response.reply:
             raise HTTPException(status_code=503, detail=ai_provider_response.reply)

        bot_message_text = ai_provider_response.reply
        found_videos: Optional[List[VideoSearchResult]] = None

        if ai_provider_response.trigger_video_search_query:
            logger.info(f"AI запросил поиск видео: '{ai_provider_response.trigger_video_search_query}'")
            videos_from_yt = await youtube_service.search_videos(
                query=ai_provider_response.trigger_video_search_query, 
                max_results=2
            )
            if videos_from_yt:
                found_videos = videos_from_yt
        
        bot_message = ChatMessage(sender="assistant", text=bot_message_text)
        await db_service.save_messages(current_session_id, [user_message, bot_message])
        
        if session_meta: # Обновляем updated_at в любом случае, если сессия существует
            session_meta.updated_at = datetime.now(timezone.utc)
            await db_service.create_or_update_session_metadata(session_meta)

        return APIChatResponseWithVideos(
            reply=bot_message.text, 
            session_id=current_session_id,
            videos=found_videos 
        )

    except HTTPException: raise
    except ConnectionError as e: raise HTTPException(status_code=503, detail="Сервис БД недоступен.")
    except Exception as e:
        logger.error(f"Ошибка в chat_router ({current_session_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@router.get("/sessions", response_model=List[SessionMetadataListResponse])
async def list_user_sessions(
    db_service: AbstractDBService = Depends(get_db_service_dependency), limit: int = 50, skip: int = 0
):
    sessions_metadata = await db_service.list_sessions_metadata(limit=limit, skip=skip)
    return [SessionMetadataListResponse(**meta.model_dump()) for meta in sessions_metadata]

@router.get("/sessions/{session_id}/history", response_model=List[ChatMessage])
async def get_session_history_route(
    session_id: str, db_service: AbstractDBService = Depends(get_db_service_dependency), limit: int = 100
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена")
    if not await db_service.delete_session_and_history(session_id):
        raise HTTPException(status_code=500, detail="Не удалось удалить сессию")
    return

@router.post("/suggestions", response_model=PersonalizedSuggestionsResponse, tags=["Suggestions"])
async def get_personalized_suggestions_route(
    request_data: PersonalizedSuggestionsRequest,
    ai_service: AbstractAIService = Depends(get_ai_service_dependency),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    history = await db_service.get_history(request_data.session_id, limit=50) if request_data.session_id else []
    suggestions = await ai_service.get_personalized_suggestions(
        conversation_history=history, preferences=request_data.preferences, system_prompt=""
    )
    return PersonalizedSuggestionsResponse(suggestions=suggestions)