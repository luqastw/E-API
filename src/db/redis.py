import redis
from src.core.config import settings

redis_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
)


def get_redis() -> redis.Redis:
    """Dependência injetável — equivalente ao get_db() do session.py."""
    try:
        yield redis_client
    finally:
        pass
