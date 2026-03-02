"""
Testes de integração para rotas de autenticação.

Testamos:
- Registro de usuário
- Login
- Validações de entrada
"""

import pytest


class TestRegister:
    """Testes para POST /auth/register."""

    def test_register_success(self, client):
        """Deve registrar usuário com sucesso."""
        response = client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "password123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["username"] == "newuser"
        assert data["is_active"] is True
        assert data["is_superuser"] is False
        assert "id" in data
        assert "hashed_password" not in data

    def test_register_duplicate_email(self, client, test_user):
        """Deve rejeitar email duplicado."""
        response = client.post(
            "/auth/register",
            json={
                "email": test_user.email,
                "username": "differentuser",
                "password": "password123",
            },
        )

        assert response.status_code == 400
        assert "Email já cadastrado" in response.json()["detail"]

    def test_register_duplicate_username(self, client, test_user):
        """Deve rejeitar username duplicado."""
        response = client.post(
            "/auth/register",
            json={
                "email": "different@example.com",
                "username": test_user.username,
                "password": "password123",
            },
        )

        assert response.status_code == 400
        assert "Username já cadastrado" in response.json()["detail"]

    def test_register_invalid_email(self, client):
        """Deve rejeitar email inválido."""
        response = client.post(
            "/auth/register",
            json={
                "email": "invalid-email",
                "username": "validuser",
                "password": "password123",
            },
        )

        assert response.status_code == 422

    def test_register_short_username(self, client):
        """Deve rejeitar username muito curto."""
        response = client.post(
            "/auth/register",
            json={
                "email": "valid@example.com",
                "username": "ab",
                "password": "password123",
            },
        )

        assert response.status_code == 422

    def test_register_short_password(self, client):
        """Deve rejeitar senha muito curta."""
        response = client.post(
            "/auth/register",
            json={
                "email": "valid@example.com",
                "username": "validuser",
                "password": "123",
            },
        )

        assert response.status_code == 422

    def test_register_long_password(self, client):
        """Deve rejeitar senha muito longa."""
        response = client.post(
            "/auth/register",
            json={
                "email": "valid@example.com",
                "username": "validuser",
                "password": "a" * 20,
            },
        )

        assert response.status_code == 422

    def test_register_missing_fields(self, client):
        """Deve rejeitar requisição sem campos obrigatórios."""
        response = client.post(
            "/auth/register",
            json={"email": "valid@example.com"},
        )

        assert response.status_code == 422


class TestLogin:
    """Testes para POST /auth/login."""

    def test_login_success(self, client, test_user):
        """Deve fazer login com sucesso."""
        response = client.post(
            "/auth/login",
            json={
                "email": test_user.email,
                "password": "password123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, test_user):
        """Deve rejeitar senha incorreta."""
        response = client.post(
            "/auth/login",
            json={
                "email": test_user.email,
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        assert "Email ou senha incorretos" in response.json()["detail"]

    def test_login_wrong_email(self, client):
        """Deve rejeitar email não cadastrado."""
        response = client.post(
            "/auth/login",
            json={
                "email": "notexists@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 401
        assert "Email ou senha incorretos" in response.json()["detail"]

    def test_login_inactive_user(self, client, test_user, db_session):
        """Deve rejeitar usuário inativo."""
        test_user.is_active = False
        db_session.commit()

        response = client.post(
            "/auth/login",
            json={
                "email": test_user.email,
                "password": "password123",
            },
        )

        assert response.status_code == 401
        assert "Conta inativa" in response.json()["detail"]

    def test_login_returns_valid_token(self, client, test_user):
        """Token retornado deve ser utilizável."""
        login_response = client.post(
            "/auth/login",
            json={
                "email": test_user.email,
                "password": "password123",
            },
        )
        token = login_response.json()["access_token"]

        protected_response = client.get(
            "/cart/",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert protected_response.status_code == 200
