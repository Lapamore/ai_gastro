# src/infrastructure/dependencies.py
import os
import logging # Добавим импорт logging
from functools import lru_cache
from dotenv import load_dotenv
from fastapi import Depends
from typing import Optional # Для _db_service_instance

from src.core.services.ai_service import AbstractAIService
from src.infrastructure.openai_client.impl import OpenAIAITunnelService # Предполагаем, что это твой AI сервис
from src.core.services.database_service import AbstractDBService
from src.infrastructure.mongodb_client.impl import MongoDBService

load_dotenv()
logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__) # Убедись, что logging импортирован

class AppConfig:
    def __init__(self):
        # ... (aitunnel переменные) ...
        self.aitunnel_api_key: str = os.getenv("AITUNNEL_API_KEY", "")
        self.aitunnel_base_url: str = os.getenv("AITUNNEL_BASE_URL", "https://api.aitunnel.ru/v1/")
        self.aitunnel_model_name: str = os.getenv("AITUNNEL_CHAT_MODEL", "gemini-1.5-flash-latest")
        self.system_prompt_file: str = os.getenv("SYSTEM_PROMPT_FILE", "./src/core/prompts/system_prompt_gastronomy.txt")
        
        self.mongodb_connection_string: str = os.getenv("MONGODB_CONNECTION_STRING", "mongodb://localhost:27017/")
        self.mongodb_database_name: str = os.getenv("MONGODB_DATABASE_NAME", "gastronomic_chat_ai")
        # Обновляем имена коллекций
        self.mongodb_chat_history_collection_name: str = os.getenv("MONGODB_CHAT_HISTORY_COLLECTION_NAME", "chat_histories")
        self.mongodb_sessions_metadata_collection_name: str = os.getenv("MONGODB_SESSIONS_METADATA_COLLECTION_NAME", "sessions_metadata")

@lru_cache()
def get_app_config() -> AppConfig:
    config = AppConfig()
    if not config.aitunnel_api_key:
        logger.warning("AITUNNEL_API_KEY не установлен в .env файле!")
    return config

async def get_ai_service_dependency(
    config: AppConfig = Depends(get_app_config)
) -> AbstractAIService:
    return OpenAIAITunnelService(
        api_key=config.aitunnel_api_key,
        base_url=config.aitunnel_base_url,
        model_name=config.aitunnel_model_name,
        system_prompt_file=config.system_prompt_file
    )

_db_service_instance: Optional[MongoDBService] = None 

async def get_db_service_dependency(
    config: AppConfig = Depends(get_app_config)
) -> AbstractDBService:
    global _db_service_instance
    if _db_service_instance is None:
        try:
            _db_service_instance = MongoDBService( 
                connection_string=config.mongodb_connection_string,
                database_name=config.mongodb_database_name,
                chat_history_collection_name=config.mongodb_chat_history_collection_name,
                sessions_metadata_collection_name=config.mongodb_sessions_metadata_collection_name
            )
            logger.info("Экземпляр MongoDBService создан и подключен.")
        except ConnectionError as e:
            logger.error(f"КРИТИЧЕСКАЯ ОШИБКА MongoDB: Не удалось создать экземпляр MongoDBService. {e}")
            raise
    return _db_service_instance

async def close_db_connection():
    global _db_service_instance
    if _db_service_instance:
        await _db_service_instance.close_connection()
        _db_service_instance = None