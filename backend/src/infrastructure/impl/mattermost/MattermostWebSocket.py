"""
WebSocket клиент для Mattermost бота.
Позволяет боту работать в личных сообщениях и каналах.
"""
import asyncio
import json
import logging
import websockets
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class MattermostWebSocketClient:
    """WebSocket клиент для прослушивания событий Mattermost"""
    
    def __init__(
        self,
        mattermost_url: str,
        bot_token: str,
        bot_user_id: Optional[str] = None,
        on_message: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        """
        Args:
            mattermost_url: URL Mattermost сервера (http://... или https://...)
            bot_token: Personal Access Token бота
            bot_user_id: ID пользователя бота (чтобы не отвечать на свои сообщения)
            on_message: Callback функция для обработки сообщений
        """
        # Конвертируем HTTP URL в WebSocket URL
        ws_url = mattermost_url.replace("https://", "wss://").replace("http://", "ws://")
        self.ws_url = f"{ws_url}/api/v4/websocket"
        self.bot_token = bot_token
        self.bot_user_id = bot_user_id
        self.on_message = on_message
        self._ws = None
        self._running = False
        self._reconnect_delay = 5  # секунд
        
    async def connect(self):
        """Подключается к WebSocket и начинает слушать события"""
        self._running = True
        
        while self._running:
            try:
                logger.info(f"Подключение к Mattermost WebSocket: {self.ws_url}")
                
                async with websockets.connect(
                    self.ws_url,
                    extra_headers={"Authorization": f"Bearer {self.bot_token}"},
                    ping_interval=30,
                    ping_timeout=10,
                ) as ws:
                    self._ws = ws
                    logger.info("WebSocket подключён успешно!")
                    
                    # Аутентификация
                    auth_msg = {
                        "seq": 1,
                        "action": "authentication_challenge",
                        "data": {"token": self.bot_token}
                    }
                    await ws.send(json.dumps(auth_msg))
                    
                    # Слушаем события
                    async for message in ws:
                        await self._handle_event(message)
                        
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket соединение закрыто: {e}")
            except Exception as e:
                logger.error(f"Ошибка WebSocket: {e}")
            
            if self._running:
                logger.info(f"Переподключение через {self._reconnect_delay} сек...")
                await asyncio.sleep(self._reconnect_delay)
    
    async def _handle_event(self, raw_message: str):
        """Обрабатывает входящее событие"""
        try:
            event = json.loads(raw_message)
            event_type = event.get("event")
            
            # Обрабатываем только новые сообщения
            if event_type == "posted":
                await self._handle_posted_event(event)
                
        except json.JSONDecodeError:
            logger.warning(f"Невозможно распарсить сообщение: {raw_message[:100]}")
        except Exception as e:
            logger.error(f"Ошибка обработки события: {e}")
    
    async def _handle_posted_event(self, event: dict):
        """Обрабатывает событие нового сообщения"""
        try:
            data = event.get("data", {})
            post_str = data.get("post", "{}")
            post = json.loads(post_str) if isinstance(post_str, str) else post_str
            
            user_id = post.get("user_id", "")
            message = post.get("message", "")
            channel_id = post.get("channel_id", "")
            
            # Игнорируем сообщения от самого бота
            if user_id == self.bot_user_id:
                return
            
            # Игнорируем пустые сообщения
            if not message.strip():
                return
            
            logger.info(f"Новое сообщение от {user_id}: {message[:50]}...")
            
            # Вызываем callback
            if self.on_message:
                await self.on_message({
                    "user_id": user_id,
                    "message": message,
                    "channel_id": channel_id,
                    "channel_type": data.get("channel_type", ""),
                    "sender_name": data.get("sender_name", ""),
                })
                
        except Exception as e:
            logger.error(f"Ошибка обработки posted события: {e}")
    
    async def disconnect(self):
        """Отключает WebSocket"""
        self._running = False
        if self._ws:
            await self._ws.close()
            logger.info("WebSocket отключён")
