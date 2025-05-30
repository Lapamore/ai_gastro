# src/infrastructure/mongodb_client/impl.py
import logging
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from datetime import datetime, timezone # Добавляем timezone для UTC
from pymongo import ReturnDocument # Для операции find_one_and_update

from src.core.services.database_service import AbstractDBService
from src.core.models import ChatMessage, SessionMetadata # Импортируем SessionMetadata

logger = logging.getLogger(__name__)

class MongoDBService(AbstractDBService):
    def __init__(self, 
                 connection_string: str, 
                 database_name: str, 
                 chat_history_collection_name: str, # Новое имя параметра
                 sessions_metadata_collection_name: str # Новый параметр
                 ):
        try:
            self.client: AsyncIOMotorClient = AsyncIOMotorClient(connection_string)
            self.db: AsyncIOMotorDatabase = self.client[database_name]
            # Используем переданные имена коллекций
            self.history_collection: AsyncIOMotorCollection = self.db[chat_history_collection_name]
            self.sessions_collection: AsyncIOMotorCollection = self.db[sessions_metadata_collection_name]
            logger.info(f"Успешно подключено к MongoDB: {database_name}. Коллекции: {chat_history_collection_name}, {sessions_metadata_collection_name}")
        except Exception as e:
            logger.error(f"Ошибка подключения к MongoDB: {e}", exc_info=True)
            raise ConnectionError(f"Не удалось подключиться к MongoDB: {e}")

    # --- Методы для истории сообщений (используем self.history_collection) ---
    async def save_message(self, session_id: str, message: ChatMessage) -> None:
        doc = {
            "session_id": session_id,
            "sender": message.sender,
            "text": message.text,
            "timestamp": message.timestamp.replace(tzinfo=timezone.utc), # Сохраняем в UTC
        }
        try:
            await self.history_collection.insert_one(doc)
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения ({session_id}): {e}", exc_info=True)

    async def save_messages(self, session_id: str, messages: List[ChatMessage]) -> None:
        if not messages: return
        docs_to_insert = [{
            "session_id": session_id,
            "sender": msg.sender,
            "text": msg.text,
            "timestamp": msg.timestamp.replace(tzinfo=timezone.utc),
        } for msg in messages]
        try:
            await self.history_collection.insert_many(docs_to_insert)
        except Exception as e:
            logger.error(f"Ошибка сохранения списка сообщений ({session_id}): {e}", exc_info=True)

    async def get_history(self, session_id: str, limit: int = 20) -> List[ChatMessage]:
        messages_data = []
        try:
            cursor = self.history_collection.find({"session_id": session_id}).sort("timestamp", -1).limit(limit)
            async for doc in cursor:
                # Убедимся, что timestamp из БД корректно обрабатывается
                ts = doc.get("timestamp")
                if isinstance(ts, datetime):
                    # Если в БД уже datetime, хорошо. Если нет, Pydantic может выдать ошибку.
                    # Если сохраняем как UTC, то при чтении тоже будет UTC.
                    pass 
                else: # Попытка сконвертировать, если это строка или что-то еще
                    try:
                        ts = datetime.fromisoformat(str(ts))
                    except:
                        ts = datetime.now(timezone.utc) # Fallback

                messages_data.append(
                    ChatMessage(sender=doc["sender"], text=doc["text"], timestamp=ts)
                )
            messages_data.reverse()
        except Exception as e:
            logger.error(f"Ошибка загрузки истории ({session_id}): {e}", exc_info=True)
        return messages_data

    # --- Новые методы для метаданных сессий (используем self.sessions_collection) ---
    async def get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        try:
            doc = await self.sessions_collection.find_one({"_id": session_id})
            if doc:
                return SessionMetadata(**doc) # Pydantic модель сама обработает _id в id
        except Exception as e:
            logger.error(f"Ошибка получения метаданных сессии {session_id}: {e}", exc_info=True)
        return None

    async def create_or_update_session_metadata(self, session_metadata: SessionMetadata) -> SessionMetadata:
        update_data = {
            "title": session_metadata.title,
            "user_id": session_metadata.user_id, # Если есть
            # "last_message_preview": session_metadata.last_message_preview, # Если есть
            "updated_at": datetime.now(timezone.utc) # Всегда ставим свежий updated_at
        }
        
        # Поле, которое устанавливается только при создании документа
        on_insert_data = {
            "created_at": session_metadata.created_at.replace(tzinfo=timezone.utc) # Берем из модели, т.к. там default_factory
        }

        # Если Pydantic модель пришла с _id (а она должна из-за alias), используем его
        session_id_for_query = session_metadata.id 

        try:
            updated_document = await self.sessions_collection.find_one_and_update(
                {"_id": session_id_for_query},  # Фильтр по _id (или session_metadata.id)
                {
                    "$set": update_data,          # Поля для обновления
                    "$setOnInsert": {             # Поля, устанавливаемые только при вставке (upsert)
                        **on_insert_data,         # Распаковываем сюда created_at
                        "_id": session_id_for_query, # Убедимся, что _id устанавливается при вставке, если его нет в фильтре (хотя он есть)
                    }
                },
                upsert=True,
                return_document=ReturnDocument.AFTER
            )
            
            if updated_document:
                 logger.info(f"Метаданные сессии {session_metadata.id} созданы/обновлены.")
                 return SessionMetadata(**updated_document)
            else:
                 logger.error(f"Не удалось создать/обновить метаданные сессии {session_metadata.id}, find_one_and_update вернул None")
                 raise Exception(f"MongoDB не вернула документ после upsert для сессии {session_metadata.id}")

        except Exception as e:
            logger.error(f"Ошибка создания/обновления метаданных сессии {session_metadata.id}: {e}", exc_info=True)
            raise # Перебрасываем ошибку, чтобы FastAPI ее обработал

    async def list_sessions_metadata(self, user_id: Optional[str] = None, limit: int = 50, skip: int = 0) -> List[SessionMetadata]:
        sessions_list = []
        query = {}
        if user_id: # Пока user_id не используется, но для будущего
            query["user_id"] = user_id
        
        try:
            cursor = self.sessions_collection.find(query).sort("updated_at", -1).skip(skip).limit(limit)
            async for doc in cursor:
                sessions_list.append(SessionMetadata(**doc))
            logger.info(f"Загружено {len(sessions_list)} метаданных сессий.")
        except Exception as e:
            logger.error(f"Ошибка загрузки списка метаданных сессий: {e}", exc_info=True)
        return sessions_list

    async def close_connection(self): # Остается как есть
        if self.client:
            self.client.close()
            logger.info("Соединение с MongoDB закрыто.")