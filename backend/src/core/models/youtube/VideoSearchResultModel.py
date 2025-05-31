from typing import Optional

from pydantic import BaseModel


class VideoSearchResult(BaseModel):
    title: str
    video_id: str
    thumbnail_url: Optional[str] = None
    channel_title: Optional[str] = None
