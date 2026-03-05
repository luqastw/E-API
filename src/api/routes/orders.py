from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from decimal import Decimal
import redis as redis_lib

from src.api.deps import get_db, get_current_user, get_current_admin, get_redis
from src.models.order import Order, OrderItem
from src.models.user import User
from src.schemas.order import (
    OrderResponse,
    OrderSummary,
    OrderUpdateStatus,
    OrderItemResponse,
)
from src.services.order_service import OrderService

router = APIRouter()


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Finalizar compra (checkout).",
    description="""Converte o carrinho em pedido de forma **atômica**:

1. Valida estoque de todos os itens
2. Cria o pedido com status `pending`
3. Copia nome e preço de cada item (snapshot imune a mudanças futuras)
4. Decrementa o estoque dos produtos
5. Limpa o carrinho

Em caso de falha em qualquer etapa, toda a operação é revertida (rollback).
""",
    response_description="Pedido criado com status `pending`.",
    responses={
        400: {"description": "Carrinho vazio ou estoque insuficiente para algum item."},
        401: {"description": "Token inválido ou ausente."},
    },
)
def checkout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    cache: redis_lib.Redis = Depends(get_redis),
) -> OrderResponse:
    """Valida estoque → cria pedido PENDING → copia itens → atualiza estoque → limpa carrinho."""
    order = OrderService.create_order(db, current_user.id)

    # histórico do usuário mudou: invalida cache de recomendações
    keys = cache.keys(f"ai:recommend:{current_user.id}:*")
    if keys:
        cache.delete(*keys)

    items_response = []
    for item in order.items:
        items_response.append(
            OrderItemResponse(
                id=item.id,
                order_id=item.order_id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                price=item.price,
                subtotal=Decimal(str(item.price)) * item.quantity,
            )
        )

    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        total_price=order.total_price,
        status=order.status,
        items=items_response,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


@router.get(
    "/",
    response_model=List[OrderSummary],
    summary="Listar pedidos do usuário.",
    description="Retorna o histórico de pedidos do usuário autenticado com paginação. Cada item é um resumo (sem detalhes dos produtos).",
    response_description="Lista de pedidos resumidos.",
    responses={
        401: {"description": "Token inválido ou ausente."},
    },
)
def list_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> List[OrderSummary]:
    orders = OrderService.get_user_orders(db, current_user.id, limit, offset)

    summaries = []
    for order in orders:
        items_count = db.query(OrderItem).filter(OrderItem.order_id == order.id).count()

        summaries.append(
            OrderSummary(
                id=order.id,
                total_price=order.total_price,
                status=order.status,
                items_count=items_count,
                created_at=order.created_at,
            )
        )

    return summaries


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Obter detalhes de um pedido.",
    description="Retorna o pedido completo com todos os itens, preços e status. Um usuário só pode ver seus próprios pedidos.",
    response_description="Pedido completo com itens.",
    responses={
        401: {"description": "Token inválido ou ausente."},
        404: {"description": "Pedido não encontrado ou não pertence ao usuário."},
    },
)
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderResponse:
    order = OrderService.get_order_by_id(db, order_id, current_user.id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {order_id} não encontrado.",
        )

    items_response = []
    for item in order.items:
        items_response.append(
            OrderItemResponse(
                id=item.id,
                order_id=item.order_id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                price=item.price,
                subtotal=Decimal(str(item.price)) * item.quantity,
            )
        )

    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        total_price=order.total_price,
        status=order.status,
        items=items_response,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


@router.patch(
    "/{order_id}/patch",
    response_model=OrderResponse,
    summary="Atualizar status de um pedido.",
    description="""Avança o status de um pedido seguindo a máquina de estados. **Somente administradores.**

Transições válidas:

| Status atual | Transições permitidas |
|--------------|-----------------------|
| `pending`    | `paid`, `cancelled`   |
| `paid`       | `shipped`, `cancelled`|
| `shipped`    | `delivered`           |
| `delivered`  | — (estado final)      |
| `cancelled`  | — (estado final)      |
""",
    response_description="Pedido com status atualizado.",
    responses={
        400: {"description": "Transição de status inválida."},
        401: {"description": "Token inválido ou ausente."},
        403: {"description": "Sem permissão. Apenas administradores."},
        404: {"description": "Pedido não encontrado."},
    },
)
def update_order_status(
    order_id: int,
    status_update: OrderUpdateStatus,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> OrderResponse:
    """Transições: pending→paid/cancelled, paid→shipped/cancelled, shipped→delivered."""
    order = OrderService.update_order_status(db, order_id, status_update.status)

    db.refresh(order)
    order = OrderService.get_order_by_id(db, order_id, order.user_id)

    items_response = []
    for item in order.items:
        items_response.append(
            OrderItemResponse(
                id=item.id,
                order_id=item.order_id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                price=item.price,
                subtotal=Decimal(str(item.price)) * item.quantity,
            )
        )

    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        total_price=order.total_price,
        status=order.status,
        items=items_response,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )
