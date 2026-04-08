from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, Field


class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    yandex_id: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    password_hash: Optional[str] = Field(default=None, exclude=True, repr=False)
    auth_provider: str = "local"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
