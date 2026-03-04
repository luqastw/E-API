from typing import List
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_current_admin
from src.models.product import Product
from src.models.enums import ProductCategory
from src.models.user import User
from src.schemas.product import ProductCreate, ProductUpdate, ProductResponse

router = APIRouter()


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar produto.",
    description="Cria um novo produto no catálogo. **Somente administradores.**",
    response_description="Produto criado com sucesso.",
    responses={
        401: {"description": "Token inválido ou ausente."},
        403: {"description": "Sem permissão. Apenas administradores."},
        422: {"description": "Dados inválidos (ex: preço negativo, categoria inexistente)."},
    },
)
def create_product(
    product_data: ProductCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ProductResponse:
    db_product = Product(
        name=product_data.name,
        description=product_data.description,
        price=product_data.price,
        category=product_data.category,
        stock=product_data.stock,
        image_url=product_data.image_url,
        is_active=True,
    )

    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    return ProductResponse.model_validate(db_product)


@router.get(
    "/",
    response_model=List[ProductResponse],
    summary="Listar produtos.",
    description="""Lista produtos ativos com suporte a filtros e paginação. **Acesso público.**

Filtros disponíveis:
- `category`: filtra por categoria (`eletronicos`, `roupas`, `livros`, `alimentos`, `esportes`, `casa`, `beleza`, `brinquedos`)
- `min_price` / `max_price`: faixa de preço em R$
- `search`: busca textual pelo nome do produto
- `limit` / `offset`: paginação
""",
    response_description="Lista de produtos ativos.",
)
def list_products(
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    category: ProductCategory | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    search: str | None = Query(default=None, min_length=1),
) -> List[ProductResponse]:
    query = db.query(Product).filter(Product.is_active == True)

    if category:
        query = query.filter(Product.category == category)

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))

    query = query.order_by(Product.id)

    products = query.offset(offset).limit(limit).all()

    return [ProductResponse.model_validate(p) for p in products]


@router.get(
    "/{product.id}",
    response_model=ProductResponse,
    summary="Obter detalhes de um produto.",
    description="Retorna os detalhes completos de um produto ativo pelo seu ID. **Acesso público.**",
    response_description="Dados do produto.",
    responses={
        404: {"description": "Produto não encontrado ou inativo."},
    },
)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductResponse:
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.is_active == True)
        .first()
    )

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto com ID {product.id} não encontrado.",
        )

    return ProductResponse.model_validate(product)


@router.patch(
    "/{product.id}",
    response_model=ProductResponse,
    summary="Atualizar produto.",
    description="Atualiza parcialmente os dados de um produto. **Somente administradores.**",
    response_description="Produto atualizado com sucesso.",
    responses={
        401: {"description": "Token inválido ou ausente."},
        403: {"description": "Sem permissão. Apenas administradores."},
        404: {"description": "Produto não encontrado."},
        422: {"description": "Dados inválidos."},
    },
)
def update_product(
    product_id: int,
    product_update: ProductUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ProductResponse:
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto com ID {product_id} não encontrado.",
        )

    update_data = product_update.model_dump(exclude_unset=True)

    if not update_data:
        return ProductResponse.model_validate(product)

    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)

    return ProductResponse.model_validate(product)


@router.delete(
    "/{product.id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar produto.",
    description="Realiza **soft delete** do produto (marca como inativo). O produto não aparece mais no catálogo, mas pedidos existentes com ele são preservados. **Somente administradores.**",
    response_description="Produto desativado. Sem conteúdo.",
    responses={
        400: {"description": "Produto já está desativado."},
        401: {"description": "Token inválido ou ausente."},
        403: {"description": "Sem permissão. Apenas administradores."},
        404: {"description": "Produto não encontrado."},
    },
)
def delete_product(
    product_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Soft delete - preserva histórico de pedidos."""
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto com ID {product_id} não encontrado.",
        )

    if not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Produto já desativado."
        )

    product.is_active = False
    db.commit()

    return None
