from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status
from decimal import Decimal
from typing import Optional

from src.models.cart import Cart, CartItem
from src.models.product import Product
from src.schemas.cart import CartItemCreate, CartItemUpdate


class CartService:

    @staticmethod
    def get_or_create_cart(db: Session, user_id: int) -> Cart:
        """1 usuário = 1 carrinho. Cria se não existe."""
        cart = db.query(Cart).filter(Cart.user_id == user_id).first()

        if cart:
            return cart

        cart = Cart(user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)

        return cart

    @staticmethod
    def add_item(db: Session, user_id: int, item_data: CartItemCreate) -> CartItem:
        """Adiciona produto ou soma quantidade se já existe no carrinho."""
        product = (
            db.query(Product)
            .filter(Product.id == item_data.product_id, Product.is_active == True)
            .first()
        )

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Produto de ID {item_data.product_id} não encontrado ou inativo.",
            )

        if product.stock < item_data.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estoque insuficiente. Disponível: {product.stock}. Solicitado: {item_data.quantity}",
            )

        cart = CartService.get_or_create_cart(db, user_id)

        existing_item = (
            db.query(CartItem)
            .filter(
                CartItem.cart_id == cart.id, CartItem.product_id == item_data.product_id
            )
            .first()
        )

        if existing_item:
            new_quantity = existing_item.quantity + item_data.quantity

            if product.stock < new_quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Estoque insuficiente. Você tem: {existing_item.quantity}. Disponível: {product.stock}.",
                )

            existing_item.quantity = new_quantity
            db.commit()
            db.refresh(existing_item)

            return existing_item

        else:
            cart_item = CartItem(
                cart_id=cart.id,
                product_id=item_data.product_id,
                quantity=item_data.quantity,
                price_at_add=product.price,
            )

            db.add(cart_item)
            db.commit()
            db.refresh(cart_item)

            return cart_item

    @staticmethod
    def update_item_quantity(
        db: Session, user_id: int, item_id: int, update_data: CartItemUpdate
    ) -> CartItem:
        cart_item = (
            db.query(CartItem)
            .join(Cart)
            .filter(CartItem.id == item_id, Cart.user_id == user_id)
            .first()
        )

        if not cart_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item não encontrado no seu carrinho.",
            )

        product = db.query(Product).filter(Product.id == cart_item.product_id).first()

        if product.stock < update_data.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estoque insuficiente. Disponível: {product.stock}",
            )

        cart_item.quantity = update_data.quantity
        db.commit()
        db.refresh(cart_item)

        return cart_item

    @staticmethod
    def remove_item(db: Session, user_id: int, item_id: int) -> None:
        cart_item = (
            db.query(CartItem)
            .join(Cart)
            .filter(CartItem.id == item_id, Cart.user_id == user_id)
            .first()
        )

        if not cart_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item não encontrado no carrinho.",
            )

        db.delete(cart_item)
        db.commit()

    @staticmethod
    def clear_cart(db: Session, user_id: int) -> None:
        cart = db.query(Cart).filter(Cart.user_id == user_id).first()

        if cart:
            db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
            db.commit()

    @staticmethod
    def get_cart_with_details(db: Session, user_id: int) -> Optional[Cart]:
        """Usa joinedload para evitar N+1 queries."""
        cart = (
            db.query(Cart)
            .options(joinedload(Cart.items).joinedload(CartItem.product))
            .filter(Cart.user_id == user_id)
            .first()
        )

        return cart

    @staticmethod
    def calculate_totals(cart: Cart) -> tuple[int, Decimal]:
        if not cart or not cart.items:
            return 0, Decimal("0.00")

        total_items = sum(item.quantity for item in cart.items)

        total_price = sum(
            Decimal(str(item.price_at_add)) * item.quantity for item in cart.items
        )

        return total_items, total_price
