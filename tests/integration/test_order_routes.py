"""
Testes de integração para rotas de pedidos.

Testamos:
- Checkout (criar pedido)
- Listar pedidos
- Obter detalhes do pedido
- Atualizar status (admin)
"""

import pytest
from src.models.enums import OrderStatus


class TestCheckout:
    """Testes para POST /orders/ (checkout)."""

    def test_checkout_success(self, client, auth_headers, test_product):
        """Deve criar pedido com sucesso."""
        client.post(
            "/cart/items",
            headers=auth_headers,
            json={"product_id": test_product.id, "quantity": 2},
        )

        response = client.post("/orders/", headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert len(data["items"]) == 1
        assert data["items"][0]["quantity"] == 2

    def test_checkout_clears_cart(self, client, auth_headers, test_product):
        """Carrinho deve estar vazio após checkout."""
        client.post(
            "/cart/items",
            headers=auth_headers,
            json={"product_id": test_product.id, "quantity": 2},
        )

        client.post("/orders/", headers=auth_headers)

        cart_response = client.get("/cart/", headers=auth_headers)
        assert len(cart_response.json()["items"]) == 0

    def test_checkout_updates_stock(self, client, auth_headers, test_product, db_session):
        """Estoque deve ser atualizado após checkout."""
        initial_stock = test_product.stock
        client.post(
            "/cart/items",
            headers=auth_headers,
            json={"product_id": test_product.id, "quantity": 2},
        )

        client.post("/orders/", headers=auth_headers)

        db_session.refresh(test_product)
        assert test_product.stock == initial_stock - 2

    def test_checkout_empty_cart(self, client, auth_headers):
        """Deve rejeitar checkout com carrinho vazio."""
        response = client.post("/orders/", headers=auth_headers)

        assert response.status_code == 400
        assert "Carrinho vazio" in response.json()["detail"]

    def test_checkout_unauthorized(self, client):
        """Deve rejeitar sem autenticação."""
        response = client.post("/orders/")

        assert response.status_code == 403


class TestListOrders:
    """Testes para GET /orders/."""

    def test_list_orders_empty(self, client, auth_headers):
        """Deve retornar lista vazia se não houver pedidos."""
        response = client.get("/orders/", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_list_orders_with_orders(self, client, auth_headers, test_product):
        """Deve listar pedidos do usuário."""
        client.post(
            "/cart/items",
            headers=auth_headers,
            json={"product_id": test_product.id, "quantity": 2},
        )
        client.post("/orders/", headers=auth_headers)

        response = client.get("/orders/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "items_count" in data[0]

    def test_list_orders_pagination(self, client, auth_headers, test_product, db_session):
        """Deve respeitar paginação."""
        for _ in range(3):
            test_product.stock = 100
            db_session.commit()
            client.post(
                "/cart/items",
                headers=auth_headers,
                json={"product_id": test_product.id, "quantity": 1},
            )
            client.post("/orders/", headers=auth_headers)

        response = client.get("/orders/?limit=2", headers=auth_headers)
        assert len(response.json()) == 2

        response = client.get("/orders/?limit=2&offset=2", headers=auth_headers)
        assert len(response.json()) == 1

    def test_list_orders_only_own(self, client, auth_headers, admin_headers, test_product):
        """Deve listar apenas pedidos do próprio usuário."""
        client.post(
            "/cart/items",
            headers=auth_headers,
            json={"product_id": test_product.id, "quantity": 1},
        )
        client.post("/orders/", headers=auth_headers)

        response = client.get("/orders/", headers=admin_headers)

        assert response.status_code == 200
        assert len(response.json()) == 0


class TestGetOrder:
    """Testes para GET /orders/{order_id}."""

    def test_get_order_success(self, client, auth_headers, test_product):
        """Deve retornar detalhes do pedido."""
        client.post(
            "/cart/items",
            headers=auth_headers,
            json={"product_id": test_product.id, "quantity": 2},
        )
        checkout_response = client.post("/orders/", headers=auth_headers)
        order_id = checkout_response.json()["id"]

        response = client.get(f"/orders/{order_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == order_id
        assert len(data["items"]) == 1

    def test_get_order_not_found(self, client, auth_headers):
        """Deve retornar 404 se pedido não existir."""
        response = client.get("/orders/99999", headers=auth_headers)

        assert response.status_code == 404

    def test_get_order_wrong_user(self, client, auth_headers, admin_headers, test_product):
        """Deve retornar 404 se pedido não pertencer ao usuário."""
        client.post(
            "/cart/items",
            headers=auth_headers,
            json={"product_id": test_product.id, "quantity": 1},
        )
        checkout_response = client.post("/orders/", headers=auth_headers)
        order_id = checkout_response.json()["id"]

        response = client.get(f"/orders/{order_id}", headers=admin_headers)

        assert response.status_code == 404


class TestUpdateOrderStatus:
    """Testes para PATCH /orders/{order_id}/patch."""

    def test_update_status_success(self, client, auth_headers, admin_headers, test_product):
        """Deve atualizar status do pedido."""
        client.post(
            "/cart/items",
            headers=auth_headers,
            json={"product_id": test_product.id, "quantity": 1},
        )
        checkout_response = client.post("/orders/", headers=auth_headers)
        order_id = checkout_response.json()["id"]

        response = client.patch(
            f"/orders/{order_id}/patch",
            headers=admin_headers,
            json={"status": "paid"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "paid"

    def test_update_status_invalid_transition(self, client, auth_headers, admin_headers, test_product):
        """Deve rejeitar transição inválida."""
        client.post(
            "/cart/items",
            headers=auth_headers,
            json={"product_id": test_product.id, "quantity": 1},
        )
        checkout_response = client.post("/orders/", headers=auth_headers)
        order_id = checkout_response.json()["id"]

        response = client.patch(
            f"/orders/{order_id}/patch",
            headers=admin_headers,
            json={"status": "delivered"},
        )

        assert response.status_code == 400
        assert "Transição inválida" in response.json()["detail"]

    def test_update_status_order_not_found(self, client, admin_headers):
        """Deve retornar 404 se pedido não existir."""
        response = client.patch(
            "/orders/99999/patch",
            headers=admin_headers,
            json={"status": "paid"},
        )

        assert response.status_code == 404

    def test_update_status_full_flow(self, client, auth_headers, admin_headers, test_product):
        """Deve permitir fluxo completo de status."""
        client.post(
            "/cart/items",
            headers=auth_headers,
            json={"product_id": test_product.id, "quantity": 1},
        )
        checkout_response = client.post("/orders/", headers=auth_headers)
        order_id = checkout_response.json()["id"]

        response = client.patch(
            f"/orders/{order_id}/patch",
            headers=admin_headers,
            json={"status": "paid"},
        )
        assert response.json()["status"] == "paid"

        response = client.patch(
            f"/orders/{order_id}/patch",
            headers=admin_headers,
            json={"status": "shipped"},
        )
        assert response.json()["status"] == "shipped"

        response = client.patch(
            f"/orders/{order_id}/patch",
            headers=admin_headers,
            json={"status": "delivered"},
        )
        assert response.json()["status"] == "delivered"
