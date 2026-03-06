import json
import numpy as np
import redis as redis_lib
from groq import Groq
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Optional

from src.core.config import settings
from src.models.product import Product
from src.models.order import Order

groq_client = Groq(api_key=settings.GROQ_API_KEY)
_embedding_model: Optional[SentenceTransformer] = None


def _get_embedding_model() -> SentenceTransformer:
    """Lazy-loads the embedding model on first use to avoid blocking at import time."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _embedding_model


class AIService:
    CHAT_MODEL = "llama-3.3-70b-versatile"

    @staticmethod
    def generate_product_embedding(product: Product) -> np.ndarray:
        text = f"""
        {product.name}
        {product.description or ""}
        Categoria: {product.category.value}
        Preço: R$ {product.price}
        """.strip()

        embedding = _get_embedding_model().encode(text)

        return embedding

    @staticmethod
    def search_similar_products(
        db: Session,
        query: str,
        limit: int = 5,
        cache: Optional[redis_lib.Redis] = None,
    ) -> List[dict]:
        """Busca semântica: vetoriza query → compara com produtos → retorna mais similares."""
        _CACHE_TTL = 300  # 5 minutos

        if cache is not None:
            cache_key = f"ai:search:{query}:{limit}"
            cached = cache.get(cache_key)

            if cached:
                # cache hit: deserializa e retorna sem tocar no banco ou no modelo
                return json.loads(cached)

        query_embedding = _get_embedding_model().encode(query)

        products = db.query(Product).filter(Product.is_active == True).all()

        if not products:
            return []

        similarities = []

        for product in products:
            product_embedding = AIService.generate_product_embedding(product)

            similarity = cosine_similarity(
                query_embedding.reshape(1, -1), product_embedding.reshape(1, -1)
            )[0][0]

            similarities.append({"product": product, "similarity": float(similarity)})

        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        result = similarities[:limit]

        if cache is not None:
            # serializa apenas os campos necessários (Product não é serializável direto)
            serializable = [
                {
                    "product": {
                        "id": item["product"].id,
                        "name": item["product"].name,
                        "description": item["product"].description,
                        "price": str(item["product"].price),
                        "category": item["product"].category.value,
                        "stock": item["product"].stock,
                        "image_url": item["product"].image_url,
                        "is_active": item["product"].is_active,
                        "created_at": item["product"].created_at.isoformat(),
                        "updated_at": item["product"].updated_at.isoformat(),
                    },
                    "similarity": item["similarity"],
                }
                for item in result
            ]
            cache.setex(cache_key, _CACHE_TTL, json.dumps(serializable))

        return result

    @staticmethod
    def get_personalized_recommendations(
        db: Session,
        user_id: int,
        limit: int = 5,
        cache: Optional[redis_lib.Redis] = None,
    ) -> List[Product]:
        """Recomenda produtos da categoria mais comprada pelo usuário."""
        _CACHE_TTL = 900  # 15 minutos

        if cache is not None:
            cache_key = f"ai:recommend:{user_id}:{limit}"
            cached = cache.get(cache_key)
            if cached:
                return json.loads(cached)

        orders = db.query(Order).filter(Order.user_id == user_id).all()

        if not orders:
            products = (
                db.query(Product)
                .filter(Product.is_active == True)
                .order_by(Product.id.desc())
                .limit(limit)
                .all()
            )
        else:
            purchased_ids = set()
            categories = []

            for order in orders:
                for item in order.items:
                    if item.product_id:
                        purchased_ids.add(item.product_id)
                        if item.product:
                            categories.append(item.product.category)

            if categories:
                favorite_category = max(set(categories), key=categories.count)

                products = (
                    db.query(Product)
                    .filter(
                        Product.is_active == True,
                        Product.category == favorite_category,
                        ~Product.id.in_(purchased_ids),
                    )
                    .limit(limit)
                    .all()
                )
            else:
                products = []

        if cache is not None and products:
            serializable = [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "price": str(p.price),
                    "category": p.category.value,
                    "stock": p.stock,
                    "image_url": p.image_url,
                    "is_active": p.is_active,
                    "created_at": p.created_at.isoformat(),
                    "updated_at": p.updated_at.isoformat(),
                }
                for p in products
            ]
            cache.setex(cache_key, _CACHE_TTL, json.dumps(serializable))

        return products

    @staticmethod
    def chat_about_products(
        db: Session,
        user_message: str,
        user_id: int = None,
        cache: Optional[redis_lib.Redis] = None,
    ) -> str:
        """Chat com RAG: busca produtos relevantes → injeta como contexto → LLM responde."""
        relevant_products = AIService.search_similar_products(db, user_message, limit=3, cache=cache)

        context = "Produtos disponíveis:\n\n"

        for i, item in enumerate(relevant_products, 1):
            p = item["product"]
            # quando vem do cache é dict; quando vem do banco é objeto ORM
            name = p["name"] if isinstance(p, dict) else p.name
            category = p["category"] if isinstance(p, dict) else p.category.value
            price = p["price"] if isinstance(p, dict) else p.price
            description = p.get("description") if isinstance(p, dict) else p.description
            stock = p["stock"] if isinstance(p, dict) else p.stock

            context += f"{i}. {name}\n"
            context += f"   Categoria: {category}\n"
            context += f"   Preço: R$ {price}\n"
            if description:
                context += f"   Descrição: {description}\n"
            context += f"   Estoque: {stock} unidades\n\n"

        response = groq_client.chat.completions.create(
            model=AIService.CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": """Você é um assistente de vendas de um e-commerce brasileiro.
                    Seja prestativo, amigável e objetivo.
                    Recomende produtos baseado APENAS no catálogo fornecido.
                    Sempre mencione preço em reais (R$) e características.
                    Se não houver produtos relevantes, seja honesto.""",
                },
                {
                    "role": "user",
                    "content": f"Contexto:\n{context}\n\nPergunta: {user_message}",
                },
            ],
            temperature=0.7,
            max_tokens=500,
        )

        return response.choices[0].message.content
