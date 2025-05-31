from typing import List, Optional
from pydantic import BaseModel, Field


class UserPreferencesData(BaseModel):
    allergies: List[str] = Field(default_factory=list)
    dietary_restrictions: List[str] = Field(
        default_factory=list, alias="dietaryRestrictions"
    )
    favorite_cuisines: List[str] = Field(default_factory=list, alias="favoriteCuisines")
    disliked_cuisines: List[str] = Field(default_factory=list, alias="dislikedCuisines")
    favorite_ingredients: List[str] = Field(
        default_factory=list, alias="favoriteIngredients"
    )
    disliked_ingredients: List[str] = Field(
        default_factory=list, alias="dislikedIngredients"
    )
    preferred_difficulty: Optional[str] = Field(
        default=None, alias="preferredDifficulty"
    )
    available_time: Optional[str] = Field(default=None, alias="availableTime")

    class Config:
        populate_by_name = True
