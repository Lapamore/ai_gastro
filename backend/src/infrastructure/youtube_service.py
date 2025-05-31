# src/infrastructure/youtube_service.py
import logging
from typing import List
import asyncio
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from src.core.models import VideoSearchResult

logger = logging.getLogger(__name__)

class YouTubeService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        if not self.api_key:
            logger.warning("API ключ YouTube не предоставлен! Поиск видео не будет работать.")
        self.youtube_service_name = "youtube"
        self.youtube_api_version = "v3"

    def _perform_search_sync(self, query: str, max_results: int) -> List[VideoSearchResult]:
        # Этот метод будет выполняться в ThreadPoolExecutor
        if not self.api_key: return []
        try:
            youtube = build(
                self.youtube_service_name, 
                self.youtube_api_version, 
                developerKey=self.api_key,
                # Отключаем дискавери кэш, т.к. он может вызывать проблемы в асинхронных/многопоточных средах
                # или при частых перезапусках uvicorn с --reload
                cache_discovery=False 
            )
            search_response = youtube.search().list(
                q=query + " рецепт",
                part="id,snippet", # Запрашиваем и id, и snippet
                type="video",
                videoEmbeddable="true",
                maxResults=max_results,
                relevanceLanguage="ru",
                # order="viewCount" # Можно сортировать по просмотрам
            ).execute()

            videos: List[VideoSearchResult] = []
            for item in search_response.get("items", []):
                video_id = item.get("id", {}).get("videoId")
                snippet = item.get("snippet", {})
                if video_id and snippet:
                    videos.append(VideoSearchResult(
                        title=snippet.get("title", "Без названия"),
                        video_id=video_id,
                        thumbnail_url=snippet.get("thumbnails", {}).get("default", {}).get("url"),
                        channel_title=snippet.get("channelTitle")
                    ))
            logger.info(f"YouTube поиск для '{query}': найдено {len(videos)} видео.")
            return videos
        except HttpError as e:
            logger.error(f"Ошибка YouTube API: {e.resp.status} - {e._get_reason()}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при поиске на YouTube: {e}", exc_info=True)
            return []

    async def search_videos(self, query: str, max_results: int = 3) -> List[VideoSearchResult]:
        if not self.api_key:
            logger.warning("Попытка поиска видео на YouTube без API ключа.")
            return []
        loop = asyncio.get_event_loop()
        # Запускаем синхронный блокирующий вызов в отдельном потоке
        return await loop.run_in_executor(None, self._perform_search_sync, query, max_results)