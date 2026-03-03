import logging
from typing import List, Optional
from datetime import datetime, timezone
import aiomysql

from src.infrastructure.interfaces.IDataBase import AbstractDBService
from src.core.models.sessions.SessionMetadataModel import SessionMetadata
from src.core.models.chatting.ChatMessageModel import ChatMessage
from src.core.models.diary.DiaryEntryModel import DiaryEntry
from src.core.models.users.UserModel import User
from src.core.models.users.UserPreferencesModel import UserPreferences

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
                # 1. Таблица пользователей
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id VARCHAR(36) PRIMARY KEY,
                        yandex_id VARCHAR(50) UNIQUE,
                        username VARCHAR(255),
                        email VARCHAR(255),
                        avatar_url VARCHAR(500),
                        created_at DATETIME NOT NULL,
                        INDEX idx_username (username),
                        INDEX idx_yandex_id (yandex_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                # Миграция: добавляем новые столбцы если их нет (для существующих БД)
                for col, col_def in [
                    ('yandex_id', 'VARCHAR(50) UNIQUE'),
                    ('email', 'VARCHAR(255)'),
                    ('avatar_url', 'VARCHAR(500)'),
                ]:
                    try:
                        await cur.execute(f"ALTER TABLE users ADD COLUMN {col} {col_def}")
                        logger.info(f"Добавлен столбец users.{col}")
                    except Exception:
                        pass  # столбец уже существует
                
                # 2. Таблица предпочтений пользователей
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL UNIQUE,
                        allergies JSON,
                        dietary_restrictions JSON,
                        favorite_cuisines JSON,
                        disliked_cuisines JSON,
                        favorite_ingredients JSON,
                        disliked_ingredients JSON,
                        preferred_difficulty VARCHAR(20),
                        available_time INT,
                        target_calories INT DEFAULT 2000,
                        weight FLOAT,
                        height FLOAT,
                        age INT,
                        gender VARCHAR(10),
                        activity_level VARCHAR(20),
                        goal VARCHAR(20),
                        target_protein FLOAT,
                        target_fat FLOAT,
                        target_carbs FLOAT,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        INDEX idx_user_id (user_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                # 3. Таблица сессий чатов
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id VARCHAR(36) PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL,
                        title VARCHAR(500) NOT NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        INDEX idx_user_id (user_id),
                        INDEX idx_updated_at (updated_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                # 4. Таблица сообщений чата
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        session_id VARCHAR(36) NOT NULL,
                        sender VARCHAR(50) NOT NULL,
                        text TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                        INDEX idx_session_id (session_id),
                        INDEX idx_timestamp (timestamp)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                # 5. Таблица дневника калорий
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS diary_entries (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        calories INT NOT NULL DEFAULT 0,
                        protein FLOAT NOT NULL DEFAULT 0,
                        fat FLOAT NOT NULL DEFAULT 0,
                        carbs FLOAT NOT NULL DEFAULT 0,
                        meal_type VARCHAR(50) NOT NULL DEFAULT 'snack',
                        timestamp DATETIME NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        INDEX idx_user_id (user_id),
                        INDEX idx_timestamp (timestamp)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                logger.info("Все 5 таблиц MySQL успешно созданы/проверены")

    # ==================== МЕТОДЫ ПОЛЬЗОВАТЕЛЕЙ ====================

    async def get_or_create_user(self, user_id: str) -> User:
        """Получить пользователя или создать нового"""
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                    row = await cur.fetchone()
                    
                    if row:
                        return User(
                            id=row['id'],
                            yandex_id=row.get('yandex_id'),
                            username=row.get('username'),
                            email=row.get('email'),
                            avatar_url=row.get('avatar_url'),
                            created_at=row['created_at'],
                        )
                    
                    # Создаём нового пользователя
                    now = datetime.now(timezone.utc)
                    await cur.execute(
                        "INSERT INTO users (id, username, created_at) VALUES (%s, %s, %s)",
                        (user_id, None, now)
                    )
                    return User(id=user_id, username=None, created_at=now)
        except Exception as e:
            logger.error(f"Ошибка get_or_create_user: {e}")
            raise

    async def get_or_create_user_by_yandex(
        self, yandex_id: str, display_name: str, email: str, avatar_id: str
    ) -> User:
        """Получить или создать пользователя по Yandex ID"""
        await self._ensure_pool()
        avatar_url = f"https://avatars.yandex.net/get-yapic/{avatar_id}/islands-200" if avatar_id else None
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    # Ищем по yandex_id
                    await cur.execute("SELECT * FROM users WHERE yandex_id = %s", (yandex_id,))
                    row = await cur.fetchone()
                    
                    if row:
                        # Обновляем имя/email/аватар на случай если они изменились
                        await cur.execute(
                            "UPDATE users SET username = %s, email = %s, avatar_url = %s WHERE yandex_id = %s",
                            (display_name, email, avatar_url, yandex_id)
                        )
                        return User(
                            id=row['id'],
                            yandex_id=row.get('yandex_id'),
                            username=display_name,
                            email=email,
                            avatar_url=avatar_url,
                            created_at=row['created_at'],
                        )
                    
                    # Создаём нового
                    import uuid
                    user_id = str(uuid.uuid4())
                    now = datetime.now(timezone.utc)
                    await cur.execute(
                        "INSERT INTO users (id, yandex_id, username, email, avatar_url, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                        (user_id, yandex_id, display_name, email, avatar_url, now)
                    )
                    return User(
                        id=user_id,
                        yandex_id=yandex_id,
                        username=display_name,
                        email=email,
                        avatar_url=avatar_url,
                        created_at=now,
                    )
        except Exception as e:
            logger.error(f"Ошибка get_or_create_user_by_yandex: {e}")
            raise

    # ==================== МЕТОДЫ ПРЕДПОЧТЕНИЙ ====================

    async def get_user_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Получить предпочтения пользователя"""
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        "SELECT * FROM user_preferences WHERE user_id = %s",
                        (user_id,)
                    )
                    row = await cur.fetchone()
                    if row:
                        return UserPreferences.from_db_row(row)
        except Exception as e:
            logger.error(f"Ошибка получения предпочтений: {e}")
        return None

    async def save_user_preferences(self, preferences: UserPreferences) -> UserPreferences:
        """Сохранить/обновить предпочтения пользователя"""
        await self._ensure_pool()
        try:
            # Убеждаемся что пользователь существует
            await self.get_or_create_user(preferences.user_id)
            
            json_data = preferences.lists_to_json()
            
            # Если есть данные тела, пересчитываем калории и БЖУ
            if preferences.weight and preferences.height and preferences.age and preferences.gender:
                calculated = preferences.calculate_tdee_and_macros()
                if calculated:
                    preferences.target_calories = calculated['target_calories']
                    preferences.target_protein = calculated['target_protein']
                    preferences.target_fat = calculated['target_fat']
                    preferences.target_carbs = calculated['target_carbs']
            
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT id FROM user_preferences WHERE user_id = %s",
                        (preferences.user_id,)
                    )
                    exists = await cur.fetchone()
                    
                    if exists:
                        await cur.execute("""
                            UPDATE user_preferences SET
                                allergies = %s,
                                dietary_restrictions = %s,
                                favorite_cuisines = %s,
                                disliked_cuisines = %s,
                                favorite_ingredients = %s,
                                disliked_ingredients = %s,
                                preferred_difficulty = %s,
                                available_time = %s,
                                target_calories = %s,
                                weight = %s,
                                height = %s,
                                age = %s,
                                gender = %s,
                                activity_level = %s,
                                goal = %s,
                                target_protein = %s,
                                target_fat = %s,
                                target_carbs = %s
                            WHERE user_id = %s
                        """, (
                            json_data['allergies'],
                            json_data['dietary_restrictions'],
                            json_data['favorite_cuisines'],
                            json_data['disliked_cuisines'],
                            json_data['favorite_ingredients'],
                            json_data['disliked_ingredients'],
                            preferences.preferred_difficulty,
                            preferences.available_time,
                            preferences.target_calories,
                            preferences.weight,
                            preferences.height,
                            preferences.age,
                            preferences.gender,
                            preferences.activity_level,
                            preferences.goal,
                            preferences.target_protein,
                            preferences.target_fat,
                            preferences.target_carbs,
                            preferences.user_id
                        ))
                    else:
                        await cur.execute("""
                            INSERT INTO user_preferences (
                                user_id, allergies, dietary_restrictions,
                                favorite_cuisines, disliked_cuisines,
                                favorite_ingredients, disliked_ingredients,
                                preferred_difficulty, available_time, target_calories,
                                weight, height, age, gender, activity_level, goal,
                                target_protein, target_fat, target_carbs
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            preferences.user_id,
                            json_data['allergies'],
                            json_data['dietary_restrictions'],
                            json_data['favorite_cuisines'],
                            json_data['disliked_cuisines'],
                            json_data['favorite_ingredients'],
                            json_data['disliked_ingredients'],
                            preferences.preferred_difficulty,
                            preferences.available_time,
                            preferences.target_calories,
                            preferences.weight,
                            preferences.height,
                            preferences.age,
                            preferences.gender,
                            preferences.activity_level,
                            preferences.goal,
                            preferences.target_protein,
                            preferences.target_fat,
                            preferences.target_carbs
                        ))
                    
                    logger.info(f"Предпочтения пользователя {preferences.user_id} сохранены")
                    return preferences
        except Exception as e:
            logger.error(f"Ошибка сохранения предпочтений: {e}")
            raise

    # ==================== МЕТОДЫ СООБЩЕНИЙ ЧАТА ====================

    async def save_message(self, session_id: str, message: ChatMessage) -> None:
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """INSERT INTO chat_messages (session_id, sender, text, timestamp) 
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
                        """INSERT INTO chat_messages (session_id, sender, text, timestamp) 
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
                        """SELECT sender, text, timestamp FROM chat_messages 
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

    # ==================== МЕТОДЫ СЕССИЙ ====================

    async def get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """SELECT id, user_id, title, created_at, updated_at 
                           FROM sessions WHERE id = %s""",
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

    async def create_or_update_session_metadata(self, session_metadata: SessionMetadata, user_id: str) -> SessionMetadata:
        await self._ensure_pool()
        try:
            # Убеждаемся что пользователь существует
            await self.get_or_create_user(user_id)
            
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    now = datetime.now(timezone.utc)
                    
                    await cur.execute("SELECT id FROM sessions WHERE id = %s", (session_metadata.id,))
                    exists = await cur.fetchone()
                    
                    if exists:
                        await cur.execute(
                            """UPDATE sessions SET title = %s, updated_at = %s WHERE id = %s""",
                            (session_metadata.title, now, session_metadata.id)
                        )
                    else:
                        await cur.execute(
                            """INSERT INTO sessions (id, user_id, title, created_at, updated_at) 
                               VALUES (%s, %s, %s, %s, %s)""",
                            (session_metadata.id, user_id, session_metadata.title,
                             session_metadata.created_at, now)
                        )
                    
                    session_metadata.user_id = user_id
                    session_metadata.updated_at = now
                    return session_metadata
        except Exception as e:
            logger.error(f"Ошибка создания/обновления сессии: {e}")
            raise

    async def list_sessions_metadata(
        self, user_id: str, limit: int = 50, skip: int = 0
    ) -> List[SessionMetadata]:
        await self._ensure_pool()
        sessions = []
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """SELECT id, user_id, title, created_at, updated_at 
                           FROM sessions 
                           WHERE user_id = %s 
                           ORDER BY updated_at DESC 
                           LIMIT %s OFFSET %s""",
                        (user_id, limit, skip)
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
                    await cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
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

    # ==================== МЕТОДЫ ДНЕВНИКА КАЛОРИЙ ====================

    async def add_diary_entry(self, user_id: str, entry: DiaryEntry) -> None:
        await self._ensure_pool()
        try:
            await self.get_or_create_user(user_id)
            
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """INSERT INTO diary_entries (user_id, name, calories, protein, fat, carbs, meal_type, timestamp) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (user_id, entry.name, entry.calories, entry.protein, entry.fat, 
                         entry.carbs, entry.meal_type, entry.timestamp)
                    )
                    logger.info(f"Запись еды сохранена для пользователя {user_id}: {entry.name}")
        except Exception as e:
            logger.error(f"Ошибка сохранения еды в MySQL: {e}", exc_info=True)

    async def get_daily_summary(self, user_id: str) -> dict:
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
                           WHERE user_id = %s AND timestamp >= %s""",
                        (user_id, today_start)
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

    async def get_today_diary_entries(self, user_id: str) -> List[DiaryEntry]:
        await self._ensure_pool()
        entries = []
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """SELECT id, name, calories, protein, fat, carbs, meal_type, timestamp 
                           FROM diary_entries 
                           WHERE user_id = %s AND timestamp >= %s 
                           ORDER BY timestamp ASC""",
                        (user_id, today_start)
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

    async def delete_diary_entry_by_name(self, user_id: str, name: str) -> bool:
        await self._ensure_pool()
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            search_name = name.strip()
            
            logger.info(f"Попытка удаления записи '{search_name}' для пользователя {user_id}")
            
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """SELECT id, name FROM diary_entries 
                           WHERE user_id = %s AND timestamp >= %s AND name LIKE %s 
                           ORDER BY timestamp DESC LIMIT 1""",
                        (user_id, today_start, f"%{search_name}%")
                    )
                    row = await cur.fetchone()
                    
                    if row:
                        await cur.execute("DELETE FROM diary_entries WHERE id = %s", (row['id'],))
                        logger.info(f"Запись '{row['name']}' успешно удалена из дневника")
                        return True
                    else:
                        logger.warning(f"Запись '{search_name}' не найдена в дневнике за сегодня")
                        return False
        except Exception as e:
            logger.error(f"Ошибка удаления записи из дневника в MySQL: {e}", exc_info=True)
            return False
