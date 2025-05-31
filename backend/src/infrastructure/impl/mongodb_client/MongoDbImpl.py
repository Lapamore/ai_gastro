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
            logger.info(
                f"Успешно подключено к MongoDB: {database_name}. Коллекции: {chat_history_collection_name}, {sessions_metadata_collection_name}"
            )
        except Exception as e:
            logger.error(f"Ошибка подключения к MongoDB: {e}", exc_info=True)
            raise ConnectionError(f"Не удалось подключиться к MongoDB: {e}")

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
            logger.error(
                f"Ошибка сохранения сообщения ({session_id}): {e}", exc_info=True
            )

    async def save_messages(self, session_id: str, messages: List[ChatMessage]) -> None:
        if not messages:
            return
        docs_to_insert = [
            {
                "session_id": session_id,
                "sender": msg.sender,
                "text": msg.text,
                "timestamp": msg.timestamp.replace(tzinfo=timezone.utc),
            }
            for msg in messages
        ]
        try:
            await self.history_collection.insert_many(docs_to_insert)
        except Exception as e:
            logger.error(
                f"Ошибка сохранения списка сообщений ({session_id}): {e}", exc_info=True
            )

    async def get_history(self, session_id: str, limit: int = 20) -> List[ChatMessage]:
        messages_data = []
        try:
            cursor = (
                self.history_collection.find({"session_id": session_id})
                .sort("timestamp", -1)
                .limit(limit)
            )
            async for doc in cursor:
                ts = doc.get("timestamp")
                if isinstance(ts, datetime):
                    pass
                else:
                    try:
                        ts = datetime.fromisoformat(str(ts))
                    except:
                        ts = datetime.now(timezone.utc)

                messages_data.append(
                    ChatMessage(sender=doc["sender"], text=doc["text"], timestamp=ts)
                )
            messages_data.reverse()
        except Exception as e:
            logger.error(f"Ошибка загрузки истории ({session_id}): {e}", exc_info=True)
        return messages_data

    async def get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        try:
            doc = await self.sessions_collection.find_one({"_id": session_id})
            if doc:
                return SessionMetadata(**doc)
        except Exception as e:
            logger.error(
                f"Ошибка получения метаданных сессии {session_id}: {e}", exc_info=True
            )
        return None

    async def create_or_update_session_metadata(
        self, session_metadata: SessionMetadata
    ) -> SessionMetadata:
        update_data = {
            "title": session_metadata.title,
            "user_id": session_metadata.user_id,
            "updated_at": datetime.now(timezone.utc),
        }

        on_insert_data = {
            "created_at": session_metadata.created_at.replace(tzinfo=timezone.utc)
        }

        session_id_for_query = session_metadata.id

        try:
            updated_document = await self.sessions_collection.find_one_and_update(
                {"_id": session_id_for_query},
                {
                    "$set": update_data,
                    "$setOnInsert": {
                        **on_insert_data,
                        "_id": session_id_for_query,
                    },
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )

            if updated_document:
                logger.info(
                    f"Метаданные сессии {session_metadata.id} созданы/обновлены."
                )
                return SessionMetadata(**updated_document)
            else:
                logger.error(
                    f"Не удалось создать/обновить метаданные сессии {session_metadata.id}, find_one_and_update вернул None"
                )
                raise Exception(
                    f"MongoDB не вернула документ после upsert для сессии {session_metadata.id}"
                )

        except Exception as e:
            logger.error(
                f"Ошибка создания/обновления метаданных сессии {session_metadata.id}: {e}",
                exc_info=True,
            )
            raise

    async def list_sessions_metadata(
        self, user_id: Optional[str] = None, limit: int = 50, skip: int = 0
    ) -> List[SessionMetadata]:
        sessions_list = []
        query = {}
        if user_id:
            query["user_id"] = user_id

        try:
            cursor = (
                self.sessions_collection.find(query)
                .sort("updated_at", -1)
                .skip(skip)
                .limit(limit)
            )
            async for doc in cursor:
                sessions_list.append(SessionMetadata(**doc))
            logger.info(f"Загружено {len(sessions_list)} метаданных сессий.")
        except Exception as e:
            logger.error(
                f"Ошибка загрузки списка метаданных сессий: {e}", exc_info=True
            )
        return sessions_list

    async def close_connection(self):
        if self.client:
            self.client.close()
            logger.info("Соединение с MongoDB закрыто.")

    async def delete_session_and_history(self, session_id: str) -> bool:
        try:
            delete_meta_result = await self.sessions_collection.delete_one(
                {"_id": session_id}
            )

            delete_history_result = await self.history_collection.delete_many(
                {"session_id": session_id}
            )

            deleted_meta_count = delete_meta_result.deleted_count
            deleted_history_count = delete_history_result.deleted_count

            if deleted_meta_count > 0:
                logger.info(
                    f"Метаданные для сессии {session_id} удалены (удалено: {deleted_meta_count}). Сообщений удалено: {deleted_history_count}."
                )
                return True
            elif deleted_history_count > 0:
                logger.info(
                    f"Метаданные для сессии {session_id} не найдены, но история сообщений удалена (удалено: {deleted_history_count})."
                )
                return True
            else:
                logger.warning(
                    f"Сессия {session_id} не найдена для удаления (ни метаданные, ни история)."
                )
                return False
        except Exception as e:
            logger.error(f"Ошибка при удалении сессии {session_id}: {e}", exc_info=True)
            return False
