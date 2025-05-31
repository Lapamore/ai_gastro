from datetime import datetime
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    sender: str
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
