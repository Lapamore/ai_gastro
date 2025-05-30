# src/core/models.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

class ChatMessage(BaseModel):
    sender: str 
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SessionMetadata(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_id: Optional[str] = None 
    title: str # Название чата
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True 
        json_encoders = {datetime: lambda dt: dt.isoformat()} 


class UserChatRequest(BaseModel):
    prompt: str
    conversation_history: List[ChatMessage] = []
    session_id: Optional[str] = None

class AIProviderResponse(BaseModel):
    reply: str

class APIChatResponse(BaseModel):
    reply: str
    session_id: str

# Новая модель для ответа со списком сессий
class SessionMetadataListResponse(BaseModel):
    id: str
    title: str
    updated_at: datetime