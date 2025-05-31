from pydantic import BaseModel


class APIChatResponse(BaseModel):
    reply: str
    session_id: str
