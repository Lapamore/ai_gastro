"""
Модели данных для интеграции с Mattermost ботом.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class MattermostWebhookRequest(BaseModel):
    """Модель входящего webhook запроса от Mattermost (Outgoing Webhook)"""
    token: str = Field(..., description="Токен для верификации webhook")
    team_id: str = Field(..., description="ID команды")
    team_domain: Optional[str] = Field(None, description="Домен команды")
    channel_id: str = Field(..., description="ID канала")
    channel_name: Optional[str] = Field(None, description="Имя канала")
    timestamp: Optional[str] = Field(None, description="Временная метка сообщения")
    user_id: str = Field(..., description="ID пользователя")
    user_name: str = Field(..., description="Имя пользователя")
    post_id: Optional[str] = Field(None, description="ID поста")
    text: str = Field(..., description="Текст сообщения")
    trigger_word: Optional[str] = Field(None, description="Триггерное слово")
    file_ids: Optional[str] = Field(None, description="ID файлов")
    
    class Config:
        extra = "allow"  # Разрешаем дополнительные поля


class MattermostSlashCommandRequest(BaseModel):
    """Модель запроса от slash-команды Mattermost"""
    token: str = Field(..., description="Токен для верификации")
    team_id: str = Field(..., description="ID команды")
    team_domain: Optional[str] = Field(None, description="Домен команды")
    channel_id: str = Field(..., description="ID канала")
    channel_name: str = Field(..., description="Имя канала")
    user_id: str = Field(..., description="ID пользователя")
    user_name: str = Field(..., description="Имя пользователя")
    command: str = Field(..., description="Введённая команда")
    text: str = Field("", description="Текст после команды")
    response_url: Optional[str] = Field(None, description="URL для отложенного ответа")
    trigger_id: Optional[str] = Field(None, description="ID триггера")


class MattermostBotResponse(BaseModel):
    """Модель ответа бота для Mattermost"""
    text: str = Field(..., description="Текст ответа")
    response_type: str = Field(
        default="in_channel",
        description="Тип ответа: 'in_channel' (виден всем) или 'ephemeral' (виден только пользователю)"
    )
    username: str = Field(default="gastro_bot", description="Имя бота (должно совпадать с Bot Account)")
    icon_url: Optional[str] = Field(
        default="https://cdn-icons-png.flaticon.com/512/1830/1830839.png",
        description="URL иконки бота"
    )


class MattermostUserAllergies(BaseModel):
    """Модель аллергий пользователя для Mattermost бота"""
    user_id: str = Field(..., description="ID пользователя Mattermost")
    allergies: List[str] = Field(default_factory=list, description="Список аллергий")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Дата обновления")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "abc123xyz",
                "allergies": ["орехи", "молоко", "глютен"],
                "updated_at": "2026-02-02T12:00:00Z"
            }
        }
