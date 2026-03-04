from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from src.models.enums import OrderStatus


class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: Optional[int] = None
    product_name: str
    quantity: int = Field(gt=0)
    price: Decimal
    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    """POST /orders com body vazio - usa carrinho do usuário autenticado."""
    pass


class OrderResponse(BaseModel):
    id: int
    user_id: int
    total_price: Decimal
    status: OrderStatus
    items: List[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderSummary(BaseModel):
    """Versão resumida para listagem (sem itens)."""
    id: int
    total_price: Decimal
    status: OrderStatus
    items_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderUpdateStatus(BaseModel):
    """Transições: pending→paid/cancelled, paid→shipped/cancelled, shipped→delivered."""
    status: Optional[OrderStatus] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "paid",
            }
        }
    )
