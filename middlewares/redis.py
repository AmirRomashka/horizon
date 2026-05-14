# middlewares/redis.py
from typing import Any, Dict, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from database.redis_client import redis_client


class RedisMiddleware(BaseMiddleware):
    """Middleware для внедрения Redis в хендлеры"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data["redis"] = redis_client
        return await handler(event, data)