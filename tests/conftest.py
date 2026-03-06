"""
Configuração global de testes.

Fixtures definidas aqui ficam disponíveis para TODOS os testes
sem precisar importar.
"""

import pytest
import fakeredis
from decimal import Decimal
from passlib.context import CryptContext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from src.main import app
from src.db.base import Base
from src.api.deps import get_db
from src.db.redis import get_redis
from src.models.user import User
from src.models.product import Product
from src.models.cart import Cart, CartItem
from src.models.enums import ProductCategory
from src.core.security import get_password_hash, create_access_token
from src.core import security

# Reduce bcrypt rounds to minimum in tests to avoid slow hashing per fixture
security.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=4)


SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=__import__("sqlalchemy.pool", fromlist=["StaticPool"]).StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """
    Cria banco limpo para cada teste (isolamento total).
    """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    Cliente HTTP com banco de teste injetado.
    """
    fake_redis = fakeredis.FakeRedis(decode_responses=True)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_redis():
        try:
            yield fake_redis
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session) -> User:
    """
    Usuário comum para testes.
    """
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_admin(db_session) -> User:
    """
    Usuário admin para testes.
    """
    admin = User(
        email="admin@example.com",
        username="adminuser",
        hashed_password=get_password_hash("admin123"),
        is_active=True,
        is_superuser=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def user_token(test_user) -> str:
    """
    Token JWT válido para usuário comum.
    """
    return create_access_token(data={"sub": str(test_user.id)})


@pytest.fixture
def admin_token(test_admin) -> str:
    """
    Token JWT válido para admin.
    """
    return create_access_token(data={"sub": str(test_admin.id)})


@pytest.fixture
def auth_headers(user_token) -> dict:
    """
    Headers de autenticação para usuário comum.
    """
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def admin_headers(admin_token) -> dict:
    """
    Headers de autenticação para admin.
    """
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def test_product(db_session) -> Product:
    """
    Produto para testes.
    """
    product = Product(
        name="Notebook Dell",
        description="Notebook Dell Inspiron 15",
        price=Decimal("3500.00"),
        category=ProductCategory.ELETRONICOS,
        stock=10,
        image_url="https://example.com/notebook.jpg",
        is_active=True,
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def test_product_out_of_stock(db_session) -> Product:
    """
    Produto sem estoque para testes.
    """
    product = Product(
        name="Mouse Logitech",
        description="Mouse sem fio",
        price=Decimal("150.00"),
        category=ProductCategory.ELETRONICOS,
        stock=0,
        is_active=True,
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def test_cart_with_items(db_session, test_user, test_product) -> Cart:
    """
    Carrinho com itens para testes.
    """
    cart = Cart(user_id=test_user.id)
    db_session.add(cart)
    db_session.commit()
    db_session.refresh(cart)

    cart_item = CartItem(
        cart_id=cart.id,
        product_id=test_product.id,
        quantity=2,
        price_at_add=test_product.price,
    )
    db_session.add(cart_item)
    db_session.commit()
    db_session.refresh(cart)

    return cart
