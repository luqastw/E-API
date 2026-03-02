"""
Testes unitários para src/services/order_service.py

Testamos:
- Criação de pedido (checkout)
- Validação de estoque
- Transições de status
- Listagem de pedidos
"""

import pytest
from decimal import Decimal
from fastapi import HTTPException

from src.services.order_service import OrderService
from src.services.cart_service import CartService
from src.schemas.cart import CartItemCreate
from src.models.order import Order, OrderItem
from src.models.enums import OrderStatus


class TestCreateOrder:
    """Testes para criação de pedido (checkout)."""

    def test_create_order_success(self, db_session, test_user, test_product):
        """Deve criar pedido com sucesso."""
        item_data = CartItemCreate(product_id=test_product.id, quantity=2)
        CartService.add_item(db_session, test_user.id, item_data)

        order = OrderService.create_order(db_session, test_user.id)

        assert order is not None
        assert order.user_id == test_user.id
        assert order.status == OrderStatus.PENDING
        assert order.total_price == Decimal("7000.00")

    def test_create_order_clears_cart(self, db_session, test_user, test_product):
        """Carrinho deve ser esvaziado após criar pedido."""
        item_data = CartItemCreate(product_id=test_product.id, quantity=2)
        CartService.add_item(db_session, test_user.id, item_data)

        OrderService.create_order(db_session, test_user.id)

        cart = CartService.get_cart_with_details(db_session, test_user.id)
        assert cart is None or len(cart.items) == 0

    def test_create_order_updates_stock(self, db_session, test_user, test_product):
        """Estoque deve ser atualizado após criar pedido."""
        initial_stock = test_product.stock
        item_data = CartItemCreate(product_id=test_product.id, quantity=2)
        CartService.add_item(db_session, test_user.id, item_data)

        OrderService.create_order(db_session, test_user.id)

        db_session.refresh(test_product)
        assert test_product.stock == initial_stock - 2

    def test_create_order_empty_cart(self, db_session, test_user):
        """Deve lançar erro se carrinho estiver vazio."""
        with pytest.raises(HTTPException) as exc_info:
            OrderService.create_order(db_session, test_user.id)

        assert exc_info.value.status_code == 400
        assert "Carrinho vazio" in str(exc_info.value.detail)

    def test_create_order_product_inactive(self, db_session, test_user, test_product):
        """Deve lançar erro se produto ficar inativo antes do checkout."""
        item_data = CartItemCreate(product_id=test_product.id, quantity=2)
        CartService.add_item(db_session, test_user.id, item_data)

        test_product.is_active = False
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            OrderService.create_order(db_session, test_user.id)

        assert exc_info.value.status_code == 400

    def test_create_order_insufficient_stock(self, db_session, test_user, test_product):
        """Deve lançar erro se estoque ficar insuficiente antes do checkout."""
        item_data = CartItemCreate(product_id=test_product.id, quantity=2)
        CartService.add_item(db_session, test_user.id, item_data)

        test_product.stock = 1
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            OrderService.create_order(db_session, test_user.id)

        assert exc_info.value.status_code == 400
        assert "Estoque insuficiente" in str(exc_info.value.detail)

    def test_create_order_creates_order_items(self, db_session, test_user, test_product):
        """Deve criar OrderItems com dados corretos."""
        item_data = CartItemCreate(product_id=test_product.id, quantity=2)
        CartService.add_item(db_session, test_user.id, item_data)

        order = OrderService.create_order(db_session, test_user.id)

        order_items = db_session.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        assert len(order_items) == 1
        assert order_items[0].product_name == test_product.name
        assert order_items[0].quantity == 2
        assert order_items[0].price == test_product.price


class TestGetUserOrders:
    """Testes para listar pedidos do usuário."""

    def test_get_user_orders_empty(self, db_session, test_user):
        """Deve retornar lista vazia se não houver pedidos."""
        orders = OrderService.get_user_orders(db_session, test_user.id)

        assert orders == []

    def test_get_user_orders_with_orders(self, db_session, test_user, test_product):
        """Deve retornar pedidos do usuário."""
        item_data = CartItemCreate(product_id=test_product.id, quantity=2)
        CartService.add_item(db_session, test_user.id, item_data)
        OrderService.create_order(db_session, test_user.id)

        orders = OrderService.get_user_orders(db_session, test_user.id)

        assert len(orders) == 1
        assert orders[0].user_id == test_user.id

    def test_get_user_orders_pagination(self, db_session, test_user, test_product):
        """Deve respeitar paginação."""
        for _ in range(3):
            test_product.stock = 100
            db_session.commit()
            item_data = CartItemCreate(product_id=test_product.id, quantity=1)
            CartService.add_item(db_session, test_user.id, item_data)
            OrderService.create_order(db_session, test_user.id)

        orders = OrderService.get_user_orders(db_session, test_user.id, limit=2, offset=0)
        assert len(orders) == 2

        orders = OrderService.get_user_orders(db_session, test_user.id, limit=2, offset=2)
        assert len(orders) == 1

    def test_get_user_orders_only_own(self, db_session, test_user, test_admin, test_product):
        """Deve retornar apenas pedidos do próprio usuário."""
        item_data = CartItemCreate(product_id=test_product.id, quantity=1)
        CartService.add_item(db_session, test_user.id, item_data)
        OrderService.create_order(db_session, test_user.id)

        orders = OrderService.get_user_orders(db_session, test_admin.id)

        assert len(orders) == 0


class TestGetOrderById:
    """Testes para buscar pedido por ID."""

    def test_get_order_by_id_success(self, db_session, test_user, test_product):
        """Deve retornar pedido se existir e pertencer ao usuário."""
        item_data = CartItemCreate(product_id=test_product.id, quantity=2)
        CartService.add_item(db_session, test_user.id, item_data)
        created_order = OrderService.create_order(db_session, test_user.id)

        order = OrderService.get_order_by_id(db_session, created_order.id, test_user.id)

        assert order is not None
        assert order.id == created_order.id

    def test_get_order_by_id_not_found(self, db_session, test_user):
        """Deve retornar None se pedido não existir."""
        order = OrderService.get_order_by_id(db_session, 99999, test_user.id)

        assert order is None

    def test_get_order_by_id_wrong_user(self, db_session, test_user, test_admin, test_product):
        """Deve retornar None se pedido não pertencer ao usuário."""
        item_data = CartItemCreate(product_id=test_product.id, quantity=2)
        CartService.add_item(db_session, test_user.id, item_data)
        created_order = OrderService.create_order(db_session, test_user.id)

        order = OrderService.get_order_by_id(db_session, created_order.id, test_admin.id)

        assert order is None


class TestValidateStatusTransition:
    """Testes para validação de transições de status."""

    @pytest.mark.parametrize("current,new,expected", [
        (OrderStatus.PENDING, OrderStatus.PAID, True),
        (OrderStatus.PENDING, OrderStatus.CANCELLED, True),
        (OrderStatus.PAID, OrderStatus.SHIPPED, True),
        (OrderStatus.PAID, OrderStatus.CANCELLED, True),
        (OrderStatus.SHIPPED, OrderStatus.DELIVERED, True),
        (OrderStatus.PENDING, OrderStatus.SHIPPED, False),
        (OrderStatus.PENDING, OrderStatus.DELIVERED, False),
        (OrderStatus.PAID, OrderStatus.PENDING, False),
        (OrderStatus.DELIVERED, OrderStatus.PENDING, False),
        (OrderStatus.DELIVERED, OrderStatus.CANCELLED, False),
        (OrderStatus.CANCELLED, OrderStatus.PENDING, False),
        (OrderStatus.CANCELLED, OrderStatus.PAID, False),
    ])
    def test_status_transitions(self, current, new, expected):
        """Deve validar transições de status corretamente."""
        result = OrderService._validate_status_transition(current, new)

        assert result == expected


class TestUpdateOrderStatus:
    """Testes para atualizar status do pedido."""

    def test_update_status_success(self, db_session, test_user, test_product):
        """Deve atualizar status com sucesso."""
        item_data = CartItemCreate(product_id=test_product.id, quantity=1)
        CartService.add_item(db_session, test_user.id, item_data)
        order = OrderService.create_order(db_session, test_user.id)

        updated_order = OrderService.update_order_status(
            db_session, order.id, OrderStatus.PAID
        )

        assert updated_order.status == OrderStatus.PAID

    def test_update_status_order_not_found(self, db_session):
        """Deve lançar erro se pedido não existir."""
        with pytest.raises(HTTPException) as exc_info:
            OrderService.update_order_status(db_session, 99999, OrderStatus.PAID)

        assert exc_info.value.status_code == 404

    def test_update_status_invalid_transition(self, db_session, test_user, test_product):
        """Deve lançar erro se transição for inválida."""
        item_data = CartItemCreate(product_id=test_product.id, quantity=1)
        CartService.add_item(db_session, test_user.id, item_data)
        order = OrderService.create_order(db_session, test_user.id)

        with pytest.raises(HTTPException) as exc_info:
            OrderService.update_order_status(
                db_session, order.id, OrderStatus.DELIVERED
            )

        assert exc_info.value.status_code == 400
        assert "Transição inválida" in str(exc_info.value.detail)

    def test_update_status_full_flow(self, db_session, test_user, test_product):
        """Deve permitir fluxo completo de status."""
        item_data = CartItemCreate(product_id=test_product.id, quantity=1)
        CartService.add_item(db_session, test_user.id, item_data)
        order = OrderService.create_order(db_session, test_user.id)

        order = OrderService.update_order_status(db_session, order.id, OrderStatus.PAID)
        assert order.status == OrderStatus.PAID

        order = OrderService.update_order_status(db_session, order.id, OrderStatus.SHIPPED)
        assert order.status == OrderStatus.SHIPPED

        order = OrderService.update_order_status(db_session, order.id, OrderStatus.DELIVERED)
        assert order.status == OrderStatus.DELIVERED

    def test_update_status_cancelled_is_final(self, db_session, test_user, test_product):
        """Status CANCELLED deve ser final."""
        item_data = CartItemCreate(product_id=test_product.id, quantity=1)
        CartService.add_item(db_session, test_user.id, item_data)
        order = OrderService.create_order(db_session, test_user.id)

        OrderService.update_order_status(db_session, order.id, OrderStatus.CANCELLED)

        with pytest.raises(HTTPException) as exc_info:
            OrderService.update_order_status(db_session, order.id, OrderStatus.PAID)

        assert exc_info.value.status_code == 400
