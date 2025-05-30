# src/services/app.py
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # Убедись, что импортировано
from dotenv import load_dotenv

from src.services.api.chat_router import router as chat_api_router
from src.infrastructure.dependencies import get_app_config, get_db_service_dependency, close_db_connection

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    app = FastAPI(
        title="Гастрономический Помощник AI (Python Backend + MongoDB)",
        description="Бэкенд для чат-бота с AITunnel, FastAPI Depends и MongoDB.",
        version="1.3.0",
    )

    origins = [
        "http://localhost:5173", 
        "http://localhost:3000", 
        "http://localhost:5174",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins, # Теперь включает твой порт
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], # Явно перечислим методы, включая OPTIONS
        allow_headers=["*"], # Или перечислить конкретные: ["Content-Type", "Authorization", "X-Session-ID"]
    )

    app.include_router(chat_api_router)
    logger.info("FastAPI приложение успешно сконфигурировано с роутерами и CORS.")

    @app.on_event("startup")
    async def startup_event():
        # ... (код startup как раньше) ...
        logger.info("Приложение запускается...")
        try:
            app_config = get_app_config()
            logger.info(f"Конфигурация загружена. Модель AI: {app_config.aitunnel_model_name}")
            await get_db_service_dependency(config=app_config)
            logger.info("Сервис базы данных успешно инициализирован.")
        except ConnectionError as e:
            logger.error(f"КРИТИЧЕСКАЯ ОШИБКА ПРИ СТАРТЕ: Не удалось подключиться к MongoDB. {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Критическая ошибка при старте приложения: {e}", exc_info=True)


    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Приложение останавливается...")
        await close_db_connection()

    @app.get("/", tags=["Root"])
    async def read_root():
        return {"message": "🤖 AI Гастро-Помощник (Python/FastAPI + MongoDB) на связи!"}

    return app

app = create_app()