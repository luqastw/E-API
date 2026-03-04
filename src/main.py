from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.api.routes import auth, users, products, cart, orders, ai

_DESCRIPTION = """
API REST de e-commerce com camada de inteligência artificial.

## Autenticação

Endpoints protegidos exigem um **Bearer token JWT** obtido via `POST /auth/login`.

```
Authorization: Bearer <token>
```

## Funcionalidades principais

- **Catálogo** — CRUD de produtos com filtros por categoria, faixa de preço e busca textual.
- **Carrinho** — Carrinho 1:1 por usuário com snapshot de preço no momento da adição.
- **Pedidos** — Checkout atômico com validação de estoque e máquina de estados de status.
- **IA** — Busca semântica por embeddings, recomendações personalizadas por histórico e chat RAG com LLaMA 3.3 70B.

## Permissões

| Role | Descrição |
|------|-----------|
| `user` | Acesso ao próprio carrinho, pedidos e perfil |
| `admin` | Gerenciamento de produtos e atualização de status de pedidos |
"""

_TAGS = [
    {
        "name": "Authentication",
        "description": "Registro de conta e login. O login retorna um **JWT Bearer token** necessário para acessar endpoints protegidos.",
    },
    {
        "name": "Users",
        "description": "Gerenciamento do perfil do usuário autenticado. Visualização, atualização e desativação de conta (soft delete).",
    },
    {
        "name": "Products",
        "description": "Catálogo de produtos. Listagem pública com filtros; criação, edição e remoção requerem permissão de **admin**.",
    },
    {
        "name": "Cart",
        "description": "Carrinho de compras. Cada usuário possui exatamente um carrinho. O preço é fixado no momento da adição do item.",
    },
    {
        "name": "Orders",
        "description": "Pedidos e checkout. O checkout converte o carrinho em pedido de forma atômica. Status segue o fluxo: `pending → paid → shipped → delivered` (ou `cancelled`).",
    },
    {
        "name": "AI",
        "description": "Camada de inteligência artificial. **Busca semântica** por embeddings, **recomendações** baseadas em histórico de compras e **chat RAG** com LLaMA 3.3 70B via Groq.",
    },
    {
        "name": "Health",
        "description": "Verificação de disponibilidade da API.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 {settings.APP_NAME} v{settings.VERSION} started!")
    print(f"📚 Documentation: http://localhost:8000/docs")
    print(f"🔒 Debug mode: {settings.DEBUG}")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    openapi_tags=_TAGS,
    contact={
        "name": "E-API",
        "url": "https://github.com/luqastw/E-API",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(cart.router, prefix="/cart", tags=["Cart"])
app.include_router(orders.router, prefix="/orders", tags=["Orders"])
app.include_router(ai.router, prefix="/ai", tags=["AI"])


@app.get(
    "/",
    tags=["Health"],
    summary="Health check.",
    description="Verifica se a API está online.",
)
def health_check():
    return {
        "status": "online",
        "message": f"{settings.APP_NAME} is running.",
        "version": settings.VERSION,
    }

