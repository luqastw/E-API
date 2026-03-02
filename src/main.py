from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.api.routes import auth, users, products, cart, orders, ai


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 {settings.APP_NAME} v{settings.VERSION} started!")
    print(f"📚 Documentation: http://localhost:8000/docs")
    print(f"🔒 Debug mode: {settings.DEBUG}")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="AI-powered e-commerce API with intelligent product recommendations",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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

