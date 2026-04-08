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
from src.core.models.recipes.SavedRecipeModel import SavedRecipe
from src.core.models.mealplan.MealPlanModels import FoodItem

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
                        password_hash TEXT,
                        auth_provider VARCHAR(20) NOT NULL DEFAULT 'local',
                        avatar_url VARCHAR(500),
                        created_at DATETIME NOT NULL,
                        INDEX idx_username (username),
                        INDEX idx_yandex_id (yandex_id),
                        INDEX idx_auth_provider (auth_provider)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                # Миграция: добавляем новые столбцы если их нет (для существующих БД)
                for col, col_def in [
                    ('yandex_id', 'VARCHAR(50) UNIQUE'),
                    ('email', 'VARCHAR(255)'),
                    ('password_hash', 'TEXT'),
                    ('auth_provider', "VARCHAR(20) NOT NULL DEFAULT 'local'"),
                    ('avatar_url', 'VARCHAR(500)'),
                ]:
                    try:
                        await cur.execute(f"ALTER TABLE users ADD COLUMN {col} {col_def}")
                        logger.info(f"Добавлен столбец users.{col}")
                    except Exception:
                        pass  # столбец уже существует

                try:
                    await cur.execute("UPDATE users SET email = NULL WHERE email = ''")
                except Exception:
                    pass

                try:
                    await cur.execute(
                        "CREATE UNIQUE INDEX idx_users_email_unique ON users (email)"
                    )
                except Exception:
                    pass

                try:
                    await cur.execute(
                        "CREATE INDEX idx_users_auth_provider ON users (auth_provider)"
                    )
                except Exception:
                    pass

                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS auth_refresh_tokens (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL,
                        token_hash CHAR(64) NOT NULL UNIQUE,
                        expires_at DATETIME NOT NULL,
                        created_at DATETIME NOT NULL,
                        revoked_at DATETIME NULL,
                        user_agent VARCHAR(500),
                        ip_address VARCHAR(64),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        INDEX idx_refresh_user_id (user_id),
                        INDEX idx_refresh_expires_at (expires_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
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

                # 6. Таблица сохранённых рецептов
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS saved_recipes (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL,
                        message_text TEXT NOT NULL,
                        rating VARCHAR(20) NOT NULL DEFAULT 'liked',
                        created_at DATETIME NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        INDEX idx_user_id (user_id),
                        INDEX idx_rating (rating)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                logger.info("Таблица saved_recipes создана/проверена")

                # 7. Справочник продуктов для ЛП-оптимизатора
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS food_items (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        calories FLOAT NOT NULL,
                        protein FLOAT NOT NULL,
                        fat FLOAT NOT NULL,
                        carbs FLOAT NOT NULL,
                        category VARCHAR(50) NOT NULL DEFAULT 'universal',
                        tags JSON,
                        allergens JSON,
                        min_portion FLOAT NOT NULL DEFAULT 50,
                        max_portion FLOAT NOT NULL DEFAULT 500,
                        INDEX idx_category (category)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)

                # Дозаполняем справочник продуктов недостающими позициями
                await self._seed_food_items(cur)
                
                logger.info("Таблица food_items создана/проверена")

    async def _seed_food_items(self, cur):
        """Заполняет справочник продуктов начальными данными (нутриенты на 100г)"""
        import json
        items = [
            # === ЗАВТРАКИ ===
            ("Овсянка на воде", 88, 3.0, 1.5, 15.5, "breakfast", ["каша","злаки"], ["глютен"], 150, 400),
            ("Яичница (2 яйца)", 196, 13.6, 15.3, 1.0, "breakfast", ["яйца"], ["яйца"], 100, 200),
            ("Творог 5%", 121, 17.2, 5.0, 1.8, "breakfast", ["молочное"], ["лактоза"], 100, 300),
            ("Йогурт натуральный", 60, 4.0, 1.5, 7.0, "breakfast", ["молочное"], ["лактоза"], 100, 300),
            ("Тост цельнозерновой", 247, 8.0, 2.5, 46.0, "breakfast", ["хлеб","злаки"], ["глютен"], 30, 120),
            ("Банан", 89, 1.1, 0.3, 22.8, "breakfast", ["фрукт"], [], 80, 200),
            ("Сырники", 183, 15.0, 8.0, 12.0, "breakfast", ["молочное","творог"], ["лактоза","яйца","глютен"], 100, 300),
            ("Блины на молоке", 170, 5.0, 3.0, 30.0, "breakfast", ["мучное"], ["глютен","лактоза","яйца"], 100, 300),
            ("Овсянка на молоке", 102, 4.0, 3.0, 16.0, "breakfast", ["каша","злаки","молочное"], ["глютен","лактоза"], 150, 400),
            ("Гранола с йогуртом", 178, 6.0, 5.5, 26.0, "breakfast", ["гранола","злаки","молочное"], ["глютен","лактоза","орехи"], 120, 250),
            ("Рисовая каша на молоке", 97, 2.6, 2.4, 17.0, "breakfast", ["каша","рис","молочное"], ["лактоза"], 150, 400),
            ("Омлет с сыром", 176, 12.5, 13.0, 1.8, "breakfast", ["яйца","сыр"], ["яйца","лактоза"], 120, 250),
            ("Творожная запеканка", 168, 14.0, 6.5, 14.0, "breakfast", ["творог","выпечка"], ["лактоза","яйца","глютен"], 120, 300),
            ("Мюсли с молоком", 124, 4.2, 3.1, 19.5, "breakfast", ["злаки","молочное"], ["глютен","лактоза","орехи"], 120, 280),
            ("Шакшука", 110, 6.5, 7.0, 5.0, "breakfast", ["яйца","овощи"], ["яйца"], 150, 300),
            ("Бутерброд с авокадо и яйцом", 185, 7.0, 10.2, 15.5, "breakfast", ["хлеб","авокадо","яйца"], ["глютен","яйца"], 80, 200),
            ("Сэндвич с индейкой", 210, 13.5, 5.5, 25.0, "breakfast", ["хлеб","индейка"], ["глютен"], 100, 220),
            ("Пшённая каша с маслом", 119, 3.0, 3.8, 18.5, "breakfast", ["каша","крупа"], [], 150, 350),
            
            # === ОБЕДЫ ===
            ("Куриная грудка варёная", 137, 29.8, 1.8, 0.5, "lunch", ["мясо","курица"], [], 100, 300),
            ("Гречка отварная", 110, 4.2, 1.1, 21.3, "lunch", ["крупа","гарнир"], [], 100, 350),
            ("Рис отварной", 116, 2.2, 0.5, 25.0, "lunch", ["крупа","гарнир"], [], 100, 350),
            ("Борщ со сметаной", 49, 1.1, 2.2, 6.7, "lunch", ["суп","овощи"], ["лактоза"], 250, 500),
            ("Котлета куриная", 167, 17.5, 8.1, 5.2, "lunch", ["мясо","курица"], ["глютен","яйца"], 80, 200),
            ("Салат из свежих овощей", 20, 1.0, 0.1, 4.0, "lunch", ["овощи","салат"], [], 100, 300),
            ("Макароны твёрдых сортов", 138, 5.0, 1.1, 27.0, "lunch", ["гарнир","мучное"], ["глютен"], 100, 300),
            ("Рыба запечённая (треска)", 82, 17.8, 0.7, 0.0, "lunch", ["рыба","морепродукты"], ["морепродукты"], 100, 300),
            ("Суп куриный с лапшой", 36, 2.4, 1.1, 3.9, "lunch", ["суп","курица"], ["глютен"], 250, 500),
            ("Говядина тушёная", 232, 16.8, 18.3, 0.0, "lunch", ["мясо"], [], 100, 250),
            ("Плов с курицей", 185, 8.5, 6.0, 24.0, "lunch", ["рис","курица","горячее"], [], 180, 400),
            ("Паста болоньезе", 176, 8.0, 6.5, 22.0, "lunch", ["паста","говядина"], ["глютен"], 180, 350),
            ("Булгур отварной", 123, 3.3, 0.3, 25.0, "lunch", ["крупа","гарнир"], ["глютен"], 100, 350),
            ("Кускус с овощами", 112, 3.8, 2.0, 19.5, "lunch", ["крупа","овощи"], ["глютен"], 150, 350),
            ("Чечевичный суп", 68, 4.5, 1.8, 9.0, "lunch", ["суп","бобовые"], [], 250, 500),
            ("Пюре картофельное", 104, 2.1, 3.8, 15.8, "lunch", ["гарнир","картофель"], ["лактоза"], 120, 350),
            ("Индейка с рисом", 154, 13.0, 3.5, 18.0, "lunch", ["индейка","рис"], [], 180, 380),
            ("Гуляш из говядины", 148, 14.0, 8.0, 4.0, "lunch", ["говядина","мясо"], [], 150, 320),
            ("Курица терияки с рисом", 165, 11.5, 3.2, 24.0, "lunch", ["курица","рис"], ["глютен"], 180, 380),
            ("Рыбные котлеты", 156, 14.0, 8.5, 7.0, "lunch", ["рыба","котлеты"], ["яйца","глютен","морепродукты"], 100, 250),
            ("Перловка с овощами", 109, 3.0, 1.1, 22.0, "lunch", ["крупа","овощи"], ["глютен"], 150, 350),
            ("Лазанья мясная", 192, 10.5, 9.0, 17.0, "lunch", ["паста","говядина","сыр"], ["глютен","лактоза"], 180, 320),
            
            # === УЖИНЫ ===
            ("Омлет с овощами", 130, 9.5, 9.0, 2.5, "dinner", ["яйца","овощи"], ["яйца","лактоза"], 150, 350),
            ("Лосось на пару", 153, 20.0, 8.1, 0.0, "dinner", ["рыба","морепродукты"], ["морепродукты"], 100, 250),
            ("Овощное рагу", 30, 0.8, 0.1, 6.5, "dinner", ["овощи","тушёное"], [], 200, 500),
            ("Куриный стейк", 150, 27.0, 4.0, 0.5, "dinner", ["мясо","курица"], [], 100, 250),
            ("Салат Цезарь", 74, 6.0, 4.2, 3.0, "dinner", ["салат","курица"], ["глютен","яйца","лактоза"], 150, 350),
            ("Тефтели в соусе", 138, 11.0, 6.0, 10.0, "dinner", ["мясо"], ["глютен","яйца"], 100, 300),
            ("Брокколи на пару", 34, 2.8, 0.4, 6.6, "dinner", ["овощи"], [], 100, 300),
            ("Индейка запечённая", 134, 22.0, 5.0, 0.0, "dinner", ["мясо","индейка"], [], 100, 300),
            ("Тушёная индейка с овощами", 126, 14.0, 4.5, 7.0, "dinner", ["индейка","овощи"], [], 180, 350),
            ("Запечённая курица с картофелем", 158, 14.0, 6.0, 11.0, "dinner", ["курица","картофель"], [], 180, 380),
            ("Паста с тунцом", 170, 12.0, 4.8, 20.0, "dinner", ["паста","рыба"], ["глютен","морепродукты"], 180, 350),
            ("Киноа с овощами", 120, 4.2, 3.2, 18.0, "dinner", ["крупа","овощи"], [], 150, 320),
            ("Греческий салат", 86, 3.2, 6.0, 4.0, "dinner", ["салат","сыр"], ["лактоза"], 150, 320),
            ("Стейк из говядины", 210, 21.0, 14.0, 0.0, "dinner", ["говядина","мясо"], [], 120, 280),
            ("Филе судака запечённое", 96, 18.5, 2.1, 0.0, "dinner", ["рыба"], ["морепродукты"], 120, 280),
            ("Рагу с фасолью", 92, 4.8, 2.2, 12.5, "dinner", ["бобовые","овощи"], [], 180, 400),
            ("Курица в сливочном соусе", 184, 16.0, 11.5, 3.0, "dinner", ["курица","соус"], ["лактоза"], 150, 300),
            ("Запечённые овощи с сыром", 95, 4.5, 5.8, 7.5, "dinner", ["овощи","сыр"], ["лактоза"], 180, 350),
            
            # === ПЕРЕКУСЫ ===
            ("Яблоко", 52, 0.3, 0.2, 13.8, "snack", ["фрукт"], [], 100, 250),
            ("Орехи грецкие", 654, 15.2, 65.2, 7.0, "snack", ["орехи"], ["орехи"], 20, 60),
            ("Кефир 1%", 40, 3.0, 1.0, 4.0, "snack", ["молочное"], ["лактоза"], 150, 400),
            ("Протеиновый батончик", 350, 30.0, 8.0, 40.0, "snack", ["спортпит"], ["глютен","лактоза"], 30, 60),
            ("Сухофрукты (курага)", 215, 5.2, 0.3, 51.0, "snack", ["сухофрукт"], [], 20, 80),
            ("Хумус", 166, 7.9, 9.6, 14.3, "snack", ["бобовые"], [], 30, 100),
            ("Морковные палочки", 35, 0.9, 0.2, 6.9, "snack", ["овощи"], [], 50, 200),
            ("Арахисовая паста", 588, 25.0, 50.0, 20.0, "snack", ["орехи"], ["орехи"], 15, 40),
            ("Греческий йогурт", 73, 5.5, 2.0, 8.0, "snack", ["молочное","йогурт"], ["лактоза"], 120, 250),
            ("Творожок ягодный", 142, 10.0, 4.0, 15.0, "snack", ["молочное","творог"], ["лактоза"], 100, 200),
            ("Финики", 282, 2.5, 0.4, 75.0, "snack", ["сухофрукт"], [], 20, 60),
            ("Смесь орехов и сухофруктов", 490, 11.0, 29.0, 42.0, "snack", ["орехи","сухофрукты"], ["орехи"], 20, 70),
            ("Банановый смузи", 96, 2.4, 1.8, 19.0, "snack", ["напиток","фрукт"], ["лактоза"], 150, 350),
            ("Сыр зернёный", 98, 11.5, 4.3, 3.2, "snack", ["молочное","сыр"], ["лактоза"], 100, 220),
            ("Овсяное печенье", 437, 6.5, 14.0, 70.0, "snack", ["выпечка","злаки"], ["глютен","яйца"], 20, 60),
            ("Хлебцы цельнозерновые", 320, 10.0, 2.8, 62.0, "snack", ["хлебцы","злаки"], ["глютен"], 20, 60),
            ("Тёмный шоколад", 546, 6.2, 35.0, 49.0, "snack", ["десерт"], [], 15, 40),
            ("Протеиновый коктейль", 118, 20.0, 1.8, 5.0, "snack", ["спортпит","напиток"], ["лактоза"], 200, 400),
            
            # === УНИВЕРСАЛЬНЫЕ ===
            ("Картофель отварной", 82, 2.0, 0.4, 16.7, "universal", ["гарнир","овощи"], [], 100, 350),
            ("Сыр твёрдый", 350, 25.0, 27.0, 0.0, "universal", ["молочное","сыр"], ["лактоза"], 20, 80),
            ("Хлеб чёрный", 201, 6.6, 1.2, 40.9, "universal", ["хлеб","злаки"], ["глютен"], 25, 100),
            ("Авокадо", 160, 2.0, 14.7, 8.5, "universal", ["фрукт","жирное"], [], 50, 200),
            ("Бурый рис", 123, 2.7, 1.0, 25.6, "universal", ["крупа","гарнир"], [], 120, 350),
            ("Киноа отварная", 120, 4.4, 1.9, 21.3, "universal", ["крупа","гарнир"], [], 100, 300),
            ("Кускус отварной", 112, 3.8, 0.2, 23.0, "universal", ["крупа","гарнир"], ["глютен"], 100, 320),
            ("Булгур с зеленью", 118, 3.7, 0.8, 23.0, "universal", ["крупа","гарнир"], ["глютен"], 120, 320),
            ("Нут отварной", 164, 8.9, 2.6, 27.4, "universal", ["бобовые","гарнир"], [], 80, 220),
            ("Фасоль красная отварная", 127, 8.7, 0.5, 22.8, "universal", ["бобовые"], [], 100, 250),
            ("Тортилья пшеничная", 310, 8.0, 7.5, 51.0, "universal", ["хлеб","лепешка"], ["глютен"], 50, 100),
            ("Лаваш тонкий", 274, 8.1, 1.2, 56.0, "universal", ["хлеб","лепешка"], ["глютен"], 40, 120),
            ("Моцарелла", 280, 18.0, 21.0, 3.0, "universal", ["сыр","молочное"], ["лактоза"], 30, 120),
            ("Гуакамоле", 180, 2.0, 16.0, 8.5, "universal", ["авокадо","соус"], [], 40, 150),
            ("Батат запечённый", 90, 1.6, 0.1, 20.7, "universal", ["гарнир","овощи"], [], 100, 300),
            ("Кукуруза консервированная", 119, 3.4, 1.4, 22.5, "universal", ["овощи","гарнир"], [], 80, 220),
            ("Хлеб цельнозерновой", 250, 9.0, 3.5, 43.0, "universal", ["хлеб","злаки"], ["глютен"], 30, 120),
        ]
        
        sql = """INSERT INTO food_items (name, calories, protein, fat, carbs, category, tags, allergens, min_portion, max_portion) 
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

        await cur.execute("SELECT name FROM food_items")
        existing_names = {row[0] for row in await cur.fetchall()}

        added_count = 0
        skipped_count = 0
        for item in items:
            if item[0] in existing_names:
                skipped_count += 1
                continue

            await cur.execute(sql, (
                item[0], item[1], item[2], item[3], item[4], item[5],
                json.dumps(item[6], ensure_ascii=False),
                json.dumps(item[7], ensure_ascii=False),
                item[8], item[9]
            ))
            existing_names.add(item[0])
            added_count += 1

        logger.info(
            f"Справочник продуктов синхронизирован: всего шаблонов={len(items)}, "
            f"добавлено={added_count}, пропущено={skipped_count}"
        )

    @staticmethod
    def _map_user_row(row: dict) -> User:
        return User(
            id=row["id"],
            yandex_id=row.get("yandex_id"),
            username=row.get("username"),
            email=row.get("email"),
            avatar_url=row.get("avatar_url"),
            password_hash=row.get("password_hash"),
            auth_provider=row.get("auth_provider") or "local",
            created_at=row["created_at"],
        )

    # ==================== МЕТОДЫ ПОЛЬЗОВАТЕЛЕЙ ====================

    async def get_or_create_user(self, user_id: str) -> User:
        """Получить пользователя или создать нового"""
        existing_user = await self.get_user_by_id(user_id)
        if existing_user:
            return existing_user

        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    now = datetime.now(timezone.utc)
                    await cur.execute(
                        """
                        INSERT INTO users (id, username, email, auth_provider, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (user_id, None, None, "local", now)
                    )
                    return User(
                        id=user_id,
                        username=None,
                        email=None,
                        auth_provider="local",
                        created_at=now,
                    )
        except Exception as e:
            logger.error(f"Ошибка get_or_create_user: {e}")
            raise

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                    row = await cur.fetchone()
                    if row:
                        return self._map_user_row(row)
        except Exception as e:
            logger.error(f"Ошибка get_user_by_id: {e}")
        return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                    row = await cur.fetchone()
                    if row:
                        return self._map_user_row(row)
        except Exception as e:
            logger.error(f"Ошибка get_user_by_email: {e}")
        return None

    async def create_local_user(self, username: str, email: str, password_hash: str) -> User:
        await self._ensure_pool()
        try:
            import uuid

            user_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO users (
                            id, username, email, password_hash, auth_provider, created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (user_id, username, email, password_hash, "local", now)
                    )
            return User(
                id=user_id,
                username=username,
                email=email,
                password_hash=password_hash,
                auth_provider="local",
                created_at=now,
            )
        except Exception as e:
            logger.error(f"Ошибка create_local_user: {e}")
            raise

    async def set_local_credentials(self, user_id: str, username: str, password_hash: str) -> User:
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE users
                        SET username = %s, password_hash = %s, auth_provider = %s
                        WHERE id = %s
                        """,
                        (username, password_hash, "local", user_id),
                    )
            user = await self.get_user_by_id(user_id)
            if not user:
                raise ValueError("Пользователь не найден после обновления локальных данных")
            return user
        except Exception as e:
            logger.error(f"Ошибка set_local_credentials: {e}")
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
                            """
                            UPDATE users
                            SET username = %s, email = %s, avatar_url = %s, auth_provider = %s
                            WHERE yandex_id = %s
                            """,
                            (display_name, email or None, avatar_url, "yandex", yandex_id)
                        )
                        row["username"] = display_name
                        row["email"] = email or None
                        row["avatar_url"] = avatar_url
                        row["auth_provider"] = "yandex"
                        return self._map_user_row(row)
                    
                    # Создаём нового
                    import uuid
                    user_id = str(uuid.uuid4())
                    now = datetime.now(timezone.utc)
                    await cur.execute(
                        """
                        INSERT INTO users (
                            id, yandex_id, username, email, avatar_url, auth_provider, created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (user_id, yandex_id, display_name, email or None, avatar_url, "yandex", now)
                    )
                    return User(
                        id=user_id,
                        yandex_id=yandex_id,
                        username=display_name,
                        email=email or None,
                        avatar_url=avatar_url,
                        auth_provider="yandex",
                        created_at=now,
                    )
        except Exception as e:
            logger.error(f"Ошибка get_or_create_user_by_yandex: {e}")
            raise

    async def store_refresh_token(
        self,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO auth_refresh_tokens (
                            user_id, token_hash, expires_at, created_at, user_agent, ip_address
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            user_id,
                            token_hash,
                            expires_at,
                            datetime.now(timezone.utc),
                            user_agent,
                            ip_address,
                        ),
                    )
        except Exception as e:
            logger.error(f"Ошибка store_refresh_token: {e}")
            raise

    async def get_user_by_refresh_token(self, token_hash: str) -> Optional[User]:
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT u.*
                        FROM auth_refresh_tokens t
                        JOIN users u ON u.id = t.user_id
                        WHERE t.token_hash = %s
                          AND t.revoked_at IS NULL
                          AND t.expires_at > %s
                        LIMIT 1
                        """,
                        (token_hash, datetime.now(timezone.utc)),
                    )
                    row = await cur.fetchone()
                    if row:
                        return self._map_user_row(row)
        except Exception as e:
            logger.error(f"Ошибка get_user_by_refresh_token: {e}")
        return None

    async def revoke_refresh_token(self, token_hash: str) -> bool:
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE auth_refresh_tokens
                        SET revoked_at = %s
                        WHERE token_hash = %s AND revoked_at IS NULL
                        """,
                        (datetime.now(timezone.utc), token_hash),
                    )
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка revoke_refresh_token: {e}")
        return False

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

    # ==================== ПРОДУКТЫ ДЛЯ ПЛАНИРОВАНИЯ ====================

    async def get_all_food_items(self) -> List[FoodItem]:
        """Получить все продукты из справочника"""
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT * FROM food_items ORDER BY category, name")
                    rows = await cur.fetchall()
                    return [FoodItem.from_db_row(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения продуктов: {e}")
            return []

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

    # ==================== СОХРАНЁННЫЕ РЕЦЕПТЫ ====================

    async def save_recipe(self, user_id: str, message_text: str, rating: str) -> SavedRecipe:
        """Сохранить рецепт (liked/disliked)"""
        await self._ensure_pool()
        now = datetime.now(timezone.utc)
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """INSERT INTO saved_recipes (user_id, message_text, rating, created_at)
                           VALUES (%s, %s, %s, %s)""",
                        (user_id, message_text, rating, now)
                    )
                    recipe_id = cur.lastrowid
                    logger.info(f"Рецепт сохранён: id={recipe_id}, rating={rating}, user={user_id}")
                    return SavedRecipe(
                        id=recipe_id,
                        user_id=user_id,
                        message_text=message_text,
                        rating=rating,
                        created_at=now
                    )
        except Exception as e:
            logger.error(f"Ошибка сохранения рецепта в MySQL: {e}", exc_info=True)
            raise

    async def get_favorite_recipes(self, user_id: str) -> List[SavedRecipe]:
        """Получить любимые рецепты (rating='liked')"""
        await self._ensure_pool()
        recipes = []
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """SELECT id, user_id, message_text, rating, created_at
                           FROM saved_recipes
                           WHERE user_id = %s AND rating = 'liked'
                           ORDER BY created_at DESC""",
                        (user_id,)
                    )
                    rows = await cur.fetchall()
                    for row in rows:
                        recipes.append(SavedRecipe(
                            id=row['id'],
                            user_id=row['user_id'],
                            message_text=row['message_text'],
                            rating=row['rating'],
                            created_at=row['created_at']
                        ))
        except Exception as e:
            logger.error(f"Ошибка получения любимых рецептов из MySQL: {e}", exc_info=True)
        return recipes

    async def delete_saved_recipe(self, recipe_id: int, user_id: str) -> bool:
        """Удалить сохранённый рецепт"""
        await self._ensure_pool()
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM saved_recipes WHERE id = %s AND user_id = %s",
                        (recipe_id, user_id)
                    )
                    deleted = cur.rowcount > 0
                    if deleted:
                        logger.info(f"Рецепт id={recipe_id} удалён для пользователя {user_id}")
                    return deleted
        except Exception as e:
            logger.error(f"Ошибка удаления рецепта из MySQL: {e}", exc_info=True)
            return False
