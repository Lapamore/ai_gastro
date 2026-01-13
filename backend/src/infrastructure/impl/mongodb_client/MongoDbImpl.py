import logging
from typing import List, Optional
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorDatabase,
    AsyncIOMotorCollection,
)
from datetime import datetime, timezone
from pymongo import ReturnDocument

from src.infrastructure.interfaces.IDataBase import AbstractDBService
from src.core.models.sessions.SessionMetadataModel import SessionMetadata
from src.core.models.chatting.ChatMessageModel import ChatMessage
from src.core.models.diary.DiaryEntryModel import DiaryEntry # Новый импорт

logger = logging.getLogger(__name__)

class MongoDBService(AbstractDBService):
    def __init__(
        self,
        connection_string: str,
        database_name: str,
        chat_history_collection_name: str,
        sessions_metadata_collection_name: str,
    ):
        try:
            self.client: AsyncIOMotorClient = AsyncIOMotorClient(connection_string)
            self.db: AsyncIOMotorDatabase = self.client[database_name]

            self.history_collection: AsyncIOMotorCollection = self.db[
                chat_history_collection_name
            ]
            self.sessions_collection: AsyncIOMotorCollection = self.db[
                sessions_metadata_collection_name
            ]
            # Новая коллекция для дневника
            self.diary_collection: AsyncIOMotorCollection = self.db["diary_entries"]
            
            logger.info(
                f"Успешно подключено к MongoDB: {database_name}. Коллекции инициализированы."
            )
        except Exception as e:
            logger.error(f"Ошибка подключения к MongoDB: {e}", exc_info=True)
            raise ConnectionError(f"Не удалось подключиться к MongoDB: {e}")

    # --- Методы чата ---

    async def save_message(self, session_id: str, message: ChatMessage) -> None:
        doc = {
            "session_id": session_id,
            "sender": message.sender,
            "text": message.text,
            "timestamp": message.timestamp.replace(tzinfo=timezone.utc),
        }
        try:
            await self.history_collection.insert_one(doc)
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения: {e}")

    async def save_messages(self, session_id: str, messages: List[ChatMessage]) -> None:
        if not messages: return
        docs = [
            {
                "session_id": session_id,
                "sender": msg.sender,
                "text": msg.text,
                "timestamp": msg.timestamp.replace(tzinfo=timezone.utc),
            } for msg in messages
        ]
        await self.history_collection.insert_many(docs)

    async def get_history(self, session_id: str, limit: int = 20) -> List[ChatMessage]:
        messages_data = []
        cursor = self.history_collection.find({"session_id": session_id}).sort("timestamp", -1).limit(limit)
        async for doc in cursor:
            messages_data.append(ChatMessage(sender=doc["sender"], text=doc["text"], timestamp=doc["timestamp"]))
        messages_data.reverse()
        return messages_data

    # --- Методы сессий ---

    async def get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        doc = await self.sessions_collection.find_one({"_id": session_id})
        return SessionMetadata(**doc) if doc else None

    async def create_or_update_session_metadata(self, session_metadata: SessionMetadata) -> SessionMetadata:
        update_data = {
            "title": session_metadata.title,
            "user_id": session_metadata.user_id,
            "updated_at": datetime.now(timezone.utc),
        }
        updated_document = await self.sessions_collection.find_one_and_update(
            {"_id": session_metadata.id},
            {"$set": update_data, "$setOnInsert": {"created_at": session_metadata.created_at.replace(tzinfo=timezone.utc), "_id": session_metadata.id}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return SessionMetadata(**updated_document)

    async def list_sessions_metadata(self, user_id: Optional[str] = None, limit: int = 50, skip: int = 0) -> List[SessionMetadata]:
        sessions_list = []
        query = {"user_id": user_id} if user_id else {}
        cursor = self.sessions_collection.find(query).sort("updated_at", -1).skip(skip).limit(limit)
        async for doc in cursor:
            sessions_list.append(SessionMetadata(**doc))
        return sessions_list

    async def delete_session_and_history(self, session_id: str) -> bool:
        await self.sessions_collection.delete_one({"_id": session_id})
        await self.history_collection.delete_many({"session_id": session_id})
        return True

    async def close_connection(self):
        self.client.close()

    # --- НОВЫЕ МЕТОДЫ ДЛЯ ДНЕВНИКА КАЛОРИЙ ---

    async def add_diary_entry(self, entry: DiaryEntry) -> None:
        try:
            doc = entry.model_dump(by_alias=True)
            # Принудительно ставим UTC для корректной агрегации
            if isinstance(doc.get('timestamp'), datetime):
                doc['timestamp'] = doc['timestamp'].replace(tzinfo=timezone.utc)
            await self.diary_collection.insert_one(doc)
            logger.info(f"Запись еды сохранена в БД: {entry.name}")
        except Exception as e:
            logger.error(f"Ошибка сохранения еды в БД: {e}", exc_info=True)

    async def get_daily_summary(self) -> dict:
        try:
            # Начало текущих суток в UTC
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            
            pipeline = [
                {"$match": {"timestamp": {"$gte": today_start}}},
                {"$group": {
                    "_id": None,
                    "totalCalories": {"$sum": "$calories"},
                    "protein": {"$sum": "$protein"},
                    "fat": {"$sum": "$fat"},
                    "carbs": {"$sum": "$carbs"}
                }}
            ]
            
            cursor = self.diary_collection.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            
            if result:
                res = result[0]
                return {
                    "totalCalories": int(res.get("totalCalories", 0)),
                    "protein": round(res.get("protein", 0), 1),
                    "fat": round(res.get("fat", 0), 1),
                    "carbs": round(res.get("carbs", 0), 1)
                }
            
            return {"totalCalories": 0, "protein": 0, "fat": 0, "carbs": 0}
        except Exception as e:
            logger.error(f"Ошибка агрегации калорий: {e}", exc_info=True)
            return {"totalCalories": 0, "protein": 0, "fat": 0, "carbs": 0}

    async def get_today_diary_entries(self) -> List[DiaryEntry]:
        """Получить все записи дневника за сегодня"""
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            
            cursor = self.diary_collection.find(
                {"timestamp": {"$gte": today_start}}
            ).sort("timestamp", 1)
            
            entries = []
            async for doc in cursor:
                entries.append(DiaryEntry(**doc))
            
            return entries
        except Exception as e:
            logger.error(f"Ошибка получения записей дневника: {e}", exc_info=True)
            return []