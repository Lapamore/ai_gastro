# src/services/api/chat_router.py
import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional # Добавим Optional
from datetime import datetime, timezone # Добавим timezone

from src.core.models import UserChatRequest, APIChatResponse, ChatMessage, SessionMetadata, SessionMetadataListResponse
from src.core.services.ai_service import AbstractAIService
from src.core.services.database_service import AbstractDBService
from src.infrastructure.dependencies import get_ai_service_dependency, get_db_service_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Chat & Sessions"]) # Обновим тег

def generate_session_title(prompt: str) -> str:
    """Генерирует простое название для сессии из первого промпта."""
    words = prompt.split()
    return " ".join(words[:5]) + ("..." if len(words) > 5 else "")


@router.post("/chat", response_model=APIChatResponse)
async def handle_chat_request(
    chat_request: UserChatRequest,
    ai_service: AbstractAIService = Depends(get_ai_service_dependency),
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    if not chat_request.prompt:
        raise HTTPException(status_code=400, detail="Сообщение пользователя (prompt) обязательно.")

    is_new_session = False
    if chat_request.session_id:
        current_session_id = chat_request.session_id
        logger.info(f"Используется существующая сессия: {current_session_id}")
        # Проверим, существует ли такая сессия в метаданных
        session_meta = await db_service.get_session_metadata(current_session_id)
        if not session_meta:
            logger.warning(f"Метаданные для сессии {current_session_id} не найдены. Будут созданы.")
            # Это странная ситуация: есть ID, но нет метаданных. Создадим их.
            title = generate_session_title(chat_request.prompt)
            new_meta = SessionMetadata(id=current_session_id, title=title)
            await db_service.create_or_update_session_metadata(new_meta)
    else:
        current_session_id = str(uuid.uuid4())
        is_new_session = True
        logger.info(f"Создана новая сессия: {current_session_id}")
        # Создаем метаданные для новой сессии
        title = generate_session_title(chat_request.prompt)
        session_meta = SessionMetadata(id=current_session_id, title=title)
        await db_service.create_or_update_session_metadata(session_meta)
    
    logger.info(f"Промпт для сессии {current_session_id}: '{chat_request.prompt[:50]}...'")

    conversation_history_from_db: List[ChatMessage] = await db_service.get_history(current_session_id, limit=10)
    logger.info(f"Загружено {len(conversation_history_from_db)} сообщений из БД для сессии {current_session_id}.")

    user_message = ChatMessage(sender="user", text=chat_request.prompt)

    try:
        ai_response_obj = await ai_service.get_ai_response(
            user_prompt=user_message.text,
            conversation_history=conversation_history_from_db, 
            system_prompt=""
        )
        
        if "Извините, произошла ошибка" in ai_response_obj.reply:
             raise HTTPException(status_code=503, detail=ai_response_obj.reply)

        bot_message = ChatMessage(sender="assistant", text=ai_response_obj.reply)

        await db_service.save_messages(current_session_id, [user_message, bot_message])
        
        # Обновляем updated_at в метаданных сессии, если она не новая (для новой already set)
        if not is_new_session and session_meta: # session_meta должно быть определено
            session_meta.updated_at = datetime.now(timezone.utc)
            # Если хотим обновить title на основе последнего промпта (опционально)
            # session_meta.title = generate_session_title(chat_request.prompt) 
            await db_service.create_or_update_session_metadata(session_meta)
        elif is_new_session and session_meta: # Для новой сессии updated_at = created_at
             pass # Уже установлено при создании

        return APIChatResponse(reply=bot_message.text, session_id=current_session_id)

    except HTTPException: raise
    except ConnectionError as e: 
        raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен.")
    except Exception as e:
        logger.error(f"Ошибка в chat_router ({current_session_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

# Новый эндпоинт для получения списка сессий
@router.get("/sessions", response_model=List[SessionMetadataListResponse])
async def list_user_sessions(
    db_service: AbstractDBService = Depends(get_db_service_dependency),
    # user_id: Optional[str] = Query(None) # Для будущей аутентификации
    limit: int = 50,
    skip: int = 0
):
    # Пока user_id не используется, получаем все сессии
    sessions_metadata = await db_service.list_sessions_metadata(user_id=None, limit=limit, skip=skip)
    
    # Преобразуем в формат ответа, если нужно (SessionMetadataListResponse)
    response_list = [
        SessionMetadataListResponse(id=meta.id, title=meta.title, updated_at=meta.updated_at)
        for meta in sessions_metadata
    ]
    return response_list

# Эндпоинт для получения истории конкретной сессии (если нужен отдельно от /chat)
@router.get("/sessions/{session_id}/history", response_model=List[ChatMessage])
async def get_session_history_route(
    session_id: str,
    db_service: AbstractDBService = Depends(get_db_service_dependency),
    limit: int = 100 # Можно больше для полной истории
):
    history = await db_service.get_history(session_id, limit=limit)
    if not history and not await db_service.get_session_metadata(session_id):
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    return history

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session_route(
    session_id: str,
    db_service: AbstractDBService = Depends(get_db_service_dependency),
):
    logger.info(f"Запрос на удаление сессии: {session_id}")
    success = await db_service.delete_session_and_history(session_id)
    if not success:
        pass
    return