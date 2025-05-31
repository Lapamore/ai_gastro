from datetime import datetime
from pydantic import BaseModel


class SessionMetadataListResponse(BaseModel):
    id: str
    title: str
    updated_at: datetime
