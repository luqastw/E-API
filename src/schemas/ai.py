from pydantic import BaseModel, Field, ConfigDict
from typing import List
from src.schemas.product import ProductResponse


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=5, max_length=2000)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Qual o melhor notebook para programação?",
            }
        }
    )


class ChatResponse(BaseModel):
    user_message: str
    ai_response: str


class SearchResultItem(BaseModel):
    product: ProductResponse
    similarity: float = Field(..., ge=0, le=1, description="Score de 0 a 1.")

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    query: str
    total: int
    results: List[SearchResultItem]


class RecommendationResponse(BaseModel):
    recommendations: List[ProductResponse]
