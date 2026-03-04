from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional
from datetime import datetime
from decimal import Decimal


class CartItemBase(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, gt=0, le=100)


class CartItemCreate(CartItemBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": 1,
                "quantity": 2,
            }
        }
    )


class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0, le=100)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "quantity": 3,
            }
        }
    )


class CartItemResponse(BaseModel):
    id: int
    cart_id: int
    product_id: int
    quantity: int
    price_at_add: Decimal
    created_at: datetime

    product_name: str
    product_image: Optional[str] = None

    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)

    @field_validator("subtotal", mode="before")
    @classmethod
    def calculate_subtotal(cls, v, info):
        if v is not None:
            return v

        data = info.data
        quantity = data.get("quantity", 1)
        price_at_add = data.get("price_at_add", 0)

        return Decimal(str(quantity)) * Decimal(str(price_at_add))


class CartResponse(BaseModel):
    id: int
    user_id: int
    items: List[CartItemResponse] = []
    total_items: int
    total_price: Decimal
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class CartSummary(BaseModel):
    """Apenas totais (para badge do carrinho na UI)."""
    total_items: int
    total_price: Decimal
