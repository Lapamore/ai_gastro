# src/services/api/chat_router.py
import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from datetime import datetime, timezone

from src.core.models import (
    UserChatRequest, APIChatResponse, ChatMessage, 
    SessionMetadata, SessionMetadataListResponse, UserPreferencesData,
    PersonalizedSuggestionsRequest, PersonalizedSuggestionsResponse
)
from src.core.services.ai_service import AbstractAIService
from src.core.services.database_service import AbstractDBService
from src.infrastructure.dependencies import get_ai_service_dependency, get_db_service_dependency

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Chat & Sessions"])

def generate_session_title(prompt: str) -> str:
    words = prompt.split()
    return " ".join(words[:5]) + ("..." if len(words) > 5 else "")

@router.post("/chat", response_model=APIChatResponse)
async def handle_chat_request(
    chat_request: UserChatRequest, # Модель теперь включает optional preferences
    ai_service: AbstractAIService = Depends(get_ai_service_dependency),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    if not chat_request.prompt:
        raise HTTPException(status_code=400, detail="Сообщение пользователя (prompt) обязательно.")

    is_new_session = False
    if chat_request.session_id:
        current_session_id = chat_request.session_id
        session_meta = await db_service.get_session_metadata(current_session_id)
        if not session_meta:
            title = generate_session_title(chat_request.prompt)
            new_meta = SessionMetadata(id=current_session_id, title=title) # created_at и updated_at по умолчанию
            session_meta = await db_service.create_or_update_session_metadata(new_meta)
            logger.warning(f"Метаданные для сессии {current_session_id} не найдены и были созданы.")
    else:
        current_session_id = str(uuid.uuid4())
        is_new_session = True
        title = generate_session_title(chat_request.prompt)
        session_meta = SessionMetadata(id=current_session_id, title=title)
        session_meta = await db_service.create_or_update_session_metadata(session_meta)
        logger.info(f"Создана новая сессия: {current_session_id}")
    
    logger.info(f"Промпт для сессии {current_session_id}: '{chat_request.prompt[:50]}...'")

    conversation_history_from_db: List[ChatMessage] = await db_service.get_history(current_session_id, limit=10)
    user_message = ChatMessage(sender="user", text=chat_request.prompt)

    # Формируем текст с предпочтениями пользователя
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
            preferences_prompt_text = "Учти следующие мои предпочтения и ограничения:\n" + "\n".join(pref_parts)
            logger.info(f"Сессия {current_session_id}: Применяются предпочтения: {pref_parts}")

    try:
        ai_response_obj = await ai_service.get_ai_response(
            user_prompt=user_message.text,
            conversation_history=conversation_history_from_db,
            system_prompt="", # Основной системный промпт из сервиса AI
            preferences_text=preferences_prompt_text # Передаем текст с предпочтениями
        )
        
        if "Извините, сервис AI временно недоступен" in ai_response_obj.reply or \
           "Извините, произошла ошибка" in ai_response_obj.reply: # Проверка на ошибки от AI сервиса
             logger.warning(f"AI сервис вернул сообщение об ошибке для сессии {current_session_id}: {ai_response_obj.reply}")
             raise HTTPException(status_code=503, detail=ai_response_obj.reply)

        bot_message = ChatMessage(sender="assistant", text=ai_response_obj.reply)
        await db_service.save_messages(current_session_id, [user_message, bot_message])
        
        if session_meta: # session_meta должно быть определено
            session_meta.updated_at = datetime.now(timezone.utc)
            # Опционально: обновлять title, если он генерируется не только из первого сообщения
            # session_meta.title = generate_session_title(chat_request.prompt) 
            await db_service.create_or_update_session_metadata(session_meta)

        return APIChatResponse(reply=bot_message.text, session_id=current_session_id)

    except HTTPException: raise
    except ConnectionError as e: 
        raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен.")
    except Exception as e:
        logger.error(f"Ошибка в chat_router ({current_session_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

# Эндпоинт GET /api/sessions и GET /api/sessions/{session_id}/history остаются без изменений

@router.get("/sessions", response_model=List[SessionMetadataListResponse])
async def list_user_sessions(
    db_service: AbstractDBService = Depends(get_db_service_dependency),
    limit: int = 50,
    skip: int = 0
):
    sessions_metadata = await db_service.list_sessions_metadata(user_id=None, limit=limit, skip=skip)
    response_list = [
        SessionMetadataListResponse(id=meta.id, title=meta.title, updated_at=meta.updated_at)
        for meta in sessions_metadata
    ]
    return response_list

@router.get("/sessions/{session_id}/history", response_model=List[ChatMessage])
async def get_session_history_route(
    session_id: str,
    db_service: AbstractDBService = Depends(get_db_service_dependency),
    limit: int = 100 
):
    history = await db_service.get_history(session_id, limit=limit)
    if not history: # Если истории нет, проверим, существует ли сессия вообще
        session_meta = await db_service.get_session_metadata(session_id)
        if not session_meta:
            raise HTTPException(status_code=404, detail="Сессия не найдена")
    return history

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session_route(
    session_id: str,
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    logger.info(f"Запрос на удаление сессии: {session_id}")
    # Сначала проверим, существует ли сессия, чтобы вернуть 404, если нет
    session_meta = await db_service.get_session_metadata(session_id)
    if not session_meta:
        logger.warning(f"Попытка удалить несуществующую сессию: {session_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена для удаления")
    
    success = await db_service.delete_session_and_history(session_id)
    if not success:
        # Эта ситуация маловероятна, если сессия существовала, но может быть ошибка при удалении
        logger.error(f"Не удалось удалить сессию {session_id} после подтверждения ее существования.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось удалить сессию")
    return # Возвращаем 204 No Content

@router.post("/suggestions", response_model=PersonalizedSuggestionsResponse, tags=["Suggestions"])
async def get_personalized_suggestions_route(
    request_data: PersonalizedSuggestionsRequest, # Принимаем sessionId и preferences
    ai_service: AbstractAIService = Depends(get_ai_service_dependency),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    logger.info(f"Запрос персонализированных предложений. Сессия: {request_data.session_id}, Преф: {'Есть' if request_data.preferences else 'Нет'}")

    history_for_suggestions: List[ChatMessage] = []
    if request_data.session_id:
        # Загружаем более полную историю для анализа предпочтений
        history_for_suggestions = await db_service.get_history(request_data.session_id, limit=50) 
    
    # Используем системный промпт, загруженный AI сервисом
    # Для get_personalized_suggestions мы передаем его явно, так как он не часть "диалога"
    # а скорее инструкция для генерации предложений.
    # Но наш AI сервис уже имеет base_system_prompt, передадим его.
    # Либо можно создать отдельный системный промпт для генерации рекомендаций.
    system_prompt_for_suggestions = "" # AI сервис использует свой базовый + промпт из метода

    try:
        suggestions_list = await ai_service.get_personalized_suggestions(
            conversation_history=history_for_suggestions,
            preferences=request_data.preferences,
            system_prompt=system_prompt_for_suggestions 
        )
        return PersonalizedSuggestionsResponse(suggestions=suggestions_list)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка в suggestions_router: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при генерации предложений.")