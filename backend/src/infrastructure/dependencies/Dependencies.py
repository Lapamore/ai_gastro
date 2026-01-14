import os
import logging
from functools import lru_cache
from fastapi import Depends
from typing import Optional

from src.infrastructure.dependencies.Config import AppConfig
from src.infrastructure.interfaces.IDataBase import AbstractDBService
from src.infrastructure.interfaces.IService import AbstractAIService
from src.infrastructure.impl.mysql_client.MySQLImpl import MySQLService
from src.infrastructure.impl.openai_client.OpenAIClient import OpenAIAITunnelService
from src.infrastructure.impl.youtube.YoutubeService import YouTubeService


logger = logging.getLogger(__name__)


@lru_cache()
def get_app_config() -> AppConfig:
    config = AppConfig()
    if not config.aitunnel_api_key:
        logger.warning("AITUNNEL_API_KEY не установлен!")
    if not config.youtube_api_key:
        logger.warning("YOUTUBE_API_KEY не установлен! Поиск видео не будет работать.")
    return config


async def get_ai_service_dependency(
    config: AppConfig = Depends(get_app_config),
) -> AbstractAIService:
    return OpenAIAITunnelService(
        api_key=config.aitunnel_api_key,
        base_url=config.aitunnel_base_url,
        model_name=config.aitunnel_model_name,
        system_prompt_file=config.system_prompt_file,
    )


_db_service_instance: Optional[MySQLService] = None


async def get_db_service_dependency(
    config: AppConfig = Depends(get_app_config),
) -> AbstractDBService:
    global _db_service_instance
    if _db_service_instance is None:
        try:
            _db_service_instance = MySQLService(
                host=config.mysql_host,
                port=config.mysql_port,
                user=config.mysql_user,
                password=config.mysql_password,
                database=config.mysql_database,
            )
        except Exception as e:
            logger.error(f"КРИТИЧЕСКАЯ ОШИБКА MySQL: {e}")
            raise
    return _db_service_instance


async def close_db_connection():
    global _db_service_instance
    if _db_service_instance:
        await _db_service_instance.close_connection()
        _db_service_instance = None


@lru_cache()
def get_youtube_service(config: AppConfig = Depends(get_app_config)) -> YouTubeService:
    return YouTubeService(api_key=config.youtube_api_key)
