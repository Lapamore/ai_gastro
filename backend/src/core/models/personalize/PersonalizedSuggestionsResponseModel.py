from typing import List
from pydantic import BaseModel


class PersonalizedSuggestionsResponse(BaseModel):
    suggestions: List[str]
