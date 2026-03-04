from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_current_user
from src.models.user import User
from src.services.ai_service import AIService
from src.schemas.ai import (
    RecommendationResponse,
    SearchResultItem,
    SearchResponse,
    ChatRequest,
    ChatResponse,
)

router = APIRouter()


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Busca semântica de produtos.",
    description="""Encontra produtos por **similaridade de significado** usando embeddings (`paraphrase-multilingual-MiniLM-L12-v2`).

Diferente da busca textual, entende sinônimos e contexto. Exemplos:
- `"fone sem fio para academia"` → encontra headphones bluetooth esportivos
- `"presente para criança pequena"` → encontra brinquedos educativos

**Acesso público.** Retorna os produtos mais similares com score de 0 a 1.
""",
    response_description="Lista de produtos ordenados por similaridade.",
    responses={
        422: {"description": "Query muito curta (mínimo 5 caracteres) ou muito longa."},
    },
)
def semantic_search(
    q: str = Query(..., min_length=5, max_length=200),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> SearchResponse:
    results = AIService.search_similar_products(db, q, limit)

    items = [
        SearchResultItem(product=item["product"], similarity=item["similarity"])
        for item in results
    ]

    return SearchResponse(query=q, total=len(items), results=items)


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat com assistente de vendas (RAG).",
    description="""Conversa com um assistente de vendas alimentado por **RAG** (Retrieval-Augmented Generation).

O sistema:
1. Vetoriza a mensagem do usuário
2. Busca os 3 produtos mais relevantes no catálogo
3. Injeta esses produtos como contexto no prompt
4. Gera a resposta via **LLaMA 3.3 70B** (Groq)

O assistente só recomenda produtos existentes no catálogo e informa preços em R$.

**Acesso público.**
""",
    response_description="Resposta do assistente baseada no catálogo.",
    responses={
        422: {"description": "Mensagem muito curta ou muito longa."},
        503: {"description": "Serviço de IA temporariamente indisponível."},
    },
)
def chat_with_ai(body: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    ai_response = AIService.chat_about_products(db, body.message)

    return ChatResponse(user_message=body.message, ai_response=ai_response)


@router.get(
    "/recommend",
    response_model=RecommendationResponse,
    summary="Recomendações personalizadas.",
    description="""Retorna produtos recomendados com base no **histórico de compras** do usuário.

Algoritmo:
1. Analisa todos os pedidos do usuário
2. Identifica a categoria mais comprada
3. Retorna produtos dessa categoria que o usuário ainda **não comprou**

Se o usuário não tiver histórico, retorna os produtos mais recentes do catálogo.
""",
    response_description="Lista de produtos recomendados.",
    responses={
        401: {"description": "Token inválido ou ausente."},
    },
)
def get_recommendations(
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    recommendations = AIService.get_personalized_recommendations(
        db, current_user.id, limit
    )

    return RecommendationResponse(recommendations=recommendations)
