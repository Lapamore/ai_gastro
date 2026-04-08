import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.services.api.ChatRouter import router as chat_router
from src.api.routes.diary_routes import router as diary_router
from src.api.routes.user_routes import router as user_router
from src.api.routes.mattermost_routes import router as mattermost_router
from src.api.routes.auth_routes import router as auth_router
from src.api.routes.recipe_routes import router as recipe_router
from src.api.routes.mealplan_routes import router as mealplan_router
from src.infrastructure.dependencies.Config import AppConfig

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Глобальная переменная для WebSocket задачи
_websocket_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global _websocket_task
    
    logger.info("Запуск приложения...")
    
    # Запускаем WebSocket бота
    from src.infrastructure.impl.mattermost.MattermostWebSocketBot import start_websocket_bot
    _websocket_task = asyncio.create_task(start_websocket_bot())
    logger.info("WebSocket бот запущен")
    
    yield
    
    # Останавливаем WebSocket
    logger.info("Выключение приложения...")
    if _websocket_task:
        _websocket_task.cancel()
        try:
            await _websocket_task
        except asyncio.CancelledError:
            pass


def create_app():
    config = AppConfig()
    app = FastAPI(lifespan=lifespan)

    # Добавляем CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Подключение роутов
    app.include_router(chat_router)  # уже имеет prefix="/api"
    app.include_router(diary_router, prefix="/api")
    app.include_router(user_router, prefix="/api")
    app.include_router(mattermost_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(recipe_router, prefix="/api")
    app.include_router(mealplan_router, prefix="/api")

    return app

app = create_app()


# Пример эндпоинта
@app.get("/")
async def read_root():
    return {"Hello": "World"}
