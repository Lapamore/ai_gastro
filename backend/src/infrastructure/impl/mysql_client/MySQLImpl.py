import logging
from typing import List, Optional
from datetime import datetime, timezone
import aiomysql

from src.infrastructure.interfaces.IDataBase import AbstractDBService
from src.core.models.sessions.SessionMetadataModel import SessionMetadata
from src.core.models.chatting.ChatMessageModel import ChatMessage
from src.core.models.diary.DiaryEntryModel import DiaryEntry

logger = logging.getLogger(__name__)


class MySQLService(AbstractDBService):
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.pool: Optional[aiomysql.Pool] = None
        logger.info(f"MySQL конфигурация инициализирована: {host}:{port}/{database}")

    async def _ensure_pool(self):
        """Создаём пул соединений при первом обращении"""
        if self.pool is None:
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                autocommit=True,
                charset='utf8mb4',
                minsize=1,
                maxsize=10,
            )
            await self._create_tables()
            logger.info("MySQL пул соединений создан и таблицы инициализированы")

    async def _create_tables(self):
        """Создаём необходимые таблицы если их нет"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Таблица сессий
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS sessions_metadata (
                        id VARCHAR(36) PRIMARY KEY,
                        user_id VARCHAR(255),
                        title VARCHAR(500) NOT NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        INDEX idx_user_id (user_id),
                        INDEX idx_updated_at (updated_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                # Таблица истории чата
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        session_id VARCHAR(36) NOT NULL,
                        sender VARCHAR(50) NOT NULL,
                        text TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        INDEX idx_session_id (session_id),
                        INDEX idx_timestamp (timestamp),
                        FOREIGN KEY (session_id) REFERENCES sessions_metadata(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                # Таблица дневника калорий
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS diary_entries (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        calories INT NOT NULL DEFAULT 0,
                        protein FLOAT NOT NULL DEFAULT 0,
                        fat FLOAT NOT NULL DEFAULT 0,
                        carbs FLOAT NOT NULL DEFAULT 0,
                        meal_type VARCHAR(50) NOT NULL DEFAULT 'snack',
                        timestamp DATETIME NOT NULL,
                        INDEX idx_timestamp (timestamp)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                logger.info("Все таблицы MySQL успешно созданы/проверены")

    # --- Методы чата ---

    async def save_message(self, session_id: str, message: ChatMessage) -> None:
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """INSERT INTO chat_history (session_id, sender, text, timestamp) 
                           VALUES (%s, %s, %s, %s)""",
                        (session_id, message.sender, message.text, message.timestamp)
                    )
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения: {e}")

    async def save_messages(self, session_id: str, messages: List[ChatMessage]) -> None:
        if not messages:
            return
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    data = [(session_id, msg.sender, msg.text, msg.timestamp) for msg in messages]
                    await cur.executemany(
                        """INSERT INTO chat_history (session_id, sender, text, timestamp) 
                           VALUES (%s, %s, %s, %s)""",
                        data
                    )
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщений: {e}")

    async def get_history(self, session_id: str, limit: int = 20) -> List[ChatMessage]:
        await self._ensure_pool()
        messages = []
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """SELECT sender, text, timestamp FROM chat_history 
                           WHERE session_id = %s 
                           ORDER BY timestamp DESC LIMIT %s""",
                        (session_id, limit)
                    )
                    rows = await cur.fetchall()
                    for row in reversed(rows):
                        messages.append(ChatMessage(
                            sender=row['sender'],
                            text=row['text'],
                            timestamp=row['timestamp']
                        ))
        except Exception as e:
            logger.error(f"Ошибка получения истории: {e}")
        return messages

    # --- Методы сессий ---

    async def get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """SELECT id, user_id, title, created_at, updated_at 
                           FROM sessions_metadata WHERE id = %s""",
                        (session_id,)
                    )
                    row = await cur.fetchone()
                    if row:
                        return SessionMetadata(
                            id=row['id'],
                            user_id=row['user_id'],
                            title=row['title'],
                            created_at=row['created_at'],
                            updated_at=row['updated_at']
                        )
        except Exception as e:
            logger.error(f"Ошибка получения метаданных сессии: {e}")
        return None

    async def create_or_update_session_metadata(self, session_metadata: SessionMetadata) -> SessionMetadata:
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    now = datetime.now(timezone.utc)
                    
                    # Проверяем существует ли сессия
                    await cur.execute(
                        "SELECT id FROM sessions_metadata WHERE id = %s",
                        (session_metadata.id,)
                    )
                    exists = await cur.fetchone()
                    
                    if exists:
                        await cur.execute(
                            """UPDATE sessions_metadata 
                               SET title = %s, user_id = %s, updated_at = %s 
                               WHERE id = %s""",
                            (session_metadata.title, session_metadata.user_id, now, session_metadata.id)
                        )
                    else:
                        await cur.execute(
                            """INSERT INTO sessions_metadata (id, user_id, title, created_at, updated_at) 
                               VALUES (%s, %s, %s, %s, %s)""",
                            (session_metadata.id, session_metadata.user_id, session_metadata.title,
                             session_metadata.created_at, now)
                        )
                    
                    session_metadata.updated_at = now
                    return session_metadata
        except Exception as e:
            logger.error(f"Ошибка создания/обновления сессии: {e}")
            raise

    async def list_sessions_metadata(
        self, user_id: Optional[str] = None, limit: int = 50, skip: int = 0
    ) -> List[SessionMetadata]:
        await self._ensure_pool()
        sessions = []
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    if user_id:
                        await cur.execute(
                            """SELECT id, user_id, title, created_at, updated_at 
                               FROM sessions_metadata 
                               WHERE user_id = %s 
                               ORDER BY updated_at DESC 
                               LIMIT %s OFFSET %s""",
                            (user_id, limit, skip)
                        )
                    else:
                        await cur.execute(
                            """SELECT id, user_id, title, created_at, updated_at 
                               FROM sessions_metadata 
                               ORDER BY updated_at DESC 
                               LIMIT %s OFFSET %s""",
                            (limit, skip)
                        )
                    
                    rows = await cur.fetchall()
                    for row in rows:
                        sessions.append(SessionMetadata(
                            id=row['id'],
                            user_id=row['user_id'],
                            title=row['title'],
                            created_at=row['created_at'],
                            updated_at=row['updated_at']
                        ))
        except Exception as e:
            logger.error(f"Ошибка получения списка сессий: {e}")
        return sessions

    async def delete_session_and_history(self, session_id: str) -> bool:
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # Удаляем сессию (история удалится каскадно)
                    await cur.execute(
                        "DELETE FROM sessions_metadata WHERE id = %s",
                        (session_id,)
                    )
                    return True
        except Exception as e:
            logger.error(f"Ошибка удаления сессии: {e}")
            return False

    async def close_connection(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None
            logger.info("MySQL пул соединений закрыт")

    # --- Методы дневника калорий ---

    async def add_diary_entry(self, entry: DiaryEntry) -> None:
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """INSERT INTO diary_entries (name, calories, protein, fat, carbs, meal_type, timestamp) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (entry.name, entry.calories, entry.protein, entry.fat, 
                         entry.carbs, entry.meal_type, entry.timestamp)
                    )
                    logger.info(f"Запись еды сохранена в MySQL: {entry.name}")
        except Exception as e:
            logger.error(f"Ошибка сохранения еды в MySQL: {e}", exc_info=True)

    async def get_daily_summary(self) -> dict:
        await self._ensure_pool()
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """SELECT 
                               COALESCE(SUM(calories), 0) as totalCalories,
                               COALESCE(SUM(protein), 0) as protein,
                               COALESCE(SUM(fat), 0) as fat,
                               COALESCE(SUM(carbs), 0) as carbs
                           FROM diary_entries 
                           WHERE timestamp >= %s""",
                        (today_start,)
                    )
                    row = await cur.fetchone()
                    
                    if row:
                        return {
                            "totalCalories": int(row['totalCalories']),
                            "protein": round(float(row['protein']), 1),
                            "fat": round(float(row['fat']), 1),
                            "carbs": round(float(row['carbs']), 1)
                        }
        except Exception as e:
            logger.error(f"Ошибка агрегации калорий в MySQL: {e}", exc_info=True)
        
        return {"totalCalories": 0, "protein": 0, "fat": 0, "carbs": 0}

    async def get_today_diary_entries(self) -> List[DiaryEntry]:
        await self._ensure_pool()
        entries = []
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """SELECT id, name, calories, protein, fat, carbs, meal_type, timestamp 
                           FROM diary_entries 
                           WHERE timestamp >= %s 
                           ORDER BY timestamp ASC""",
                        (today_start,)
                    )
                    rows = await cur.fetchall()
                    
                    for row in rows:
                        entries.append(DiaryEntry(
                            id=str(row['id']),
                            name=row['name'],
                            calories=row['calories'],
                            protein=row['protein'],
                            fat=row['fat'],
                            carbs=row['carbs'],
                            meal_type=row['meal_type'],
                            timestamp=row['timestamp']
                        ))
        except Exception as e:
            logger.error(f"Ошибка получения записей дневника из MySQL: {e}", exc_info=True)
        
        return entries

    async def delete_diary_entry_by_name(self, name: str) -> bool:
        await self._ensure_pool()
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            search_name = name.strip()
            
            logger.info(f"Попытка удаления записи '{search_name}' за сегодня (с {today_start})")
            
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    # Сначала ищем запись
                    await cur.execute(
                        """SELECT id, name FROM diary_entries 
                           WHERE timestamp >= %s AND name LIKE %s 
                           ORDER BY timestamp DESC LIMIT 1""",
                        (today_start, f"%{search_name}%")
                    )
                    row = await cur.fetchone()
                    
                    if row:
                        await cur.execute(
                            "DELETE FROM diary_entries WHERE id = %s",
                            (row['id'],)
                        )
                        logger.info(f"Запись '{row['name']}' успешно удалена из дневника")
                        return True
                    else:
                        logger.warning(f"Запись '{search_name}' не найдена в дневнике за сегодня")
                        return False
        except Exception as e:
            logger.error(f"Ошибка удаления записи из дневника в MySQL: {e}", exc_info=True)
            return False
