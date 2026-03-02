from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from fastapi import HTTPException, status
from decimal import Decimal
from typing import List, Optional

from src.models.order import Order, OrderItem
from src.models.cart import Cart, CartItem
from src.models.enums import OrderStatus
from src.services.cart_service import CartService


class OrderService:

    @staticmethod
    def create_order(db: Session, user_id: int) -> Order:
        """Checkout: valida estoque → cria Order PENDING → copia itens → atualiza estoque → limpa carrinho."""
        cart = (
            db.query(Cart)
            .options(joinedload(Cart.items).joinedload(CartItem.product))
            .filter(Cart.user_id == user_id)
            .first()
        )

        if not cart or not cart.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Carrinho vazio. Adicione produtos antes de finalizar a compra.",
            )

        for cart_item in cart.items:
            product = cart_item.product

            if not product or not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Produto '{cart_item.product.name if product else 'desconhecido'}' não está mais disponível.",
                )

            if product.stock < cart_item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Estoque insuficiente para '{product.name}'. "
                        f"Disponível: {product.stock}, "
                        f"no carrinho: {cart_item.quantity}"
                    ),
                )

        total_price = sum(
            Decimal(str(item.price_at_add)) * item.quantity for item in cart.items
        )

        order = Order(
            user_id=user_id, total_price=total_price, status=OrderStatus.PENDING
        )

        db.add(order)
        db.flush()

        order_items = []

        for cart_item in cart.items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=cart_item.product_id,
                product_name=cart_item.product.name,
                quantity=cart_item.quantity,
                price=cart_item.price_at_add,
            )
            order_items.append(order_item)

        db.add_all(order_items)

        for cart_item in cart.items:
            product = cart_item.product
            product.stock -= cart_item.quantity

            if product.stock < 0:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Erro ao atualizar estoque de '{product.name}'",
                )

        CartService.clear_cart(db, user_id)

        db.commit()
        db.refresh(order)
        order = (
            db.query(Order)
            .options(joinedload(Order.items))
            .filter(Order.user_id == user_id)
            .first()
        )

        return order

    @staticmethod
    def get_user_orders(
        db: Session, user_id: int, limit: int = 10, offset: int = 0
    ) -> List[Order]:
        orders = (
            db.query(Order)
            .filter(Order.user_id == user_id)
            .order_by(desc(Order.created_at))
            .limit(limit)
            .offset(offset)
            .all()
        )

        return orders

    @staticmethod
    def get_order_by_id(db: Session, order_id: int, user_id: int) -> Optional[Order]:
        order = (
            db.query(Order)
            .options(joinedload(Order.items))
            .filter(Order.user_id == user_id, Order.id == order_id)
            .first()
        )

        return order

    @staticmethod
    def _validate_status_transition(
        current_status: OrderStatus, new_status: OrderStatus
    ) -> bool:
        """Transições válidas: pending→paid/cancelled, paid→shipped/cancelled, shipped→delivered."""
        if current_status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
            return False

        valid_transitions = {
            OrderStatus.PENDING: [OrderStatus.PAID, OrderStatus.CANCELLED],
            OrderStatus.PAID: [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
            OrderStatus.SHIPPED: [OrderStatus.DELIVERED],
        }

        allowed_statuses = valid_transitions.get(current_status, [])
        return new_status in allowed_statuses

    @staticmethod
    def update_order_status(
        db: Session, order_id: int, new_status: OrderStatus
    ) -> Order:
        order = db.query(Order).filter(Order.id == order_id).first()

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pedido {order_id} não encontrado.",
            )

        if not OrderService._validate_status_transition(order.status, new_status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Transição inválida: {order.status.value} → {new_status.value}. "
                    f"Verifique as regras de transição de status."
                ),
            )

        order.status = new_status
        db.commit()
        db.refresh(order)

        return order
