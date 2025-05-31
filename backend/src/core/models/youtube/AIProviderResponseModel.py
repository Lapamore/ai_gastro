from typing import Optional
from pydantic import BaseModel


class AIProviderResponse(BaseModel):
    reply: str
    trigger_video_search_query: Optional[str] = None
