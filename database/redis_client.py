# database/redis_client.py
import json
from typing import Optional, Any, Dict
from icecream import ic
import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from config import REDIS_URL


class RedisClient:
    """Клиент для работы с Redis"""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self._pool: Optional[ConnectionPool] = None
    
    async def connect(self):
        """Подключение к Redis"""
        if not self._pool:
            self._pool = ConnectionPool.from_url(REDIS_URL, decode_responses=True)
            self.redis = redis.Redis(connection_pool=self._pool)
            ic("✅ Redis connected")
    
    async def disconnect(self):
        """Отключение от Redis"""
        if self.redis:
            await self.redis.close()
            await self._pool.disconnect()
            ic("❌ Redis disconnected")
    
    async def set(self, key: str, value: Any, expire: int = None) -> bool:
        """Сохранить значение по ключу"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            else:
                value = str(value)
            
            if expire:
                await self.redis.setex(key, expire, value)
            else:
                await self.redis.set(key, value)
            return True
        except Exception as e:
            ic(f"Redis set error: {e}")
            return False
    
    async def get(self, key: str, as_json: bool = False) -> Optional[Any]:
        """Получить значение по ключу"""
        try:
            value = await self.redis.get(key)
            if value and as_json:
                return json.loads(value)
            return value
        except Exception as e:
            ic(f"Redis get error: {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        """Удалить ключ"""
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            ic(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Проверить существование ключа"""
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            ic(f"Redis exists error: {e}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Установить TTL для ключа"""
        try:
            return await self.redis.expire(key, seconds)
        except Exception as e:
            ic(f"Redis expire error: {e}")
            return False
    
    async def incr(self, key: str) -> int:
        """Инкремент значения"""
        try:
            return await self.redis.incr(key)
        except Exception as e:
            ic(f"Redis incr error: {e}")
            return 0
    
    async def sadd(self, key: str, *values) -> int:
        """Добавить в множество"""
        try:
            return await self.redis.sadd(key, *values)
        except Exception as e:
            ic(f"Redis sadd error: {e}")
            return 0
    
    async def srem(self, key: str, *values) -> int:
        """Удалить из множества"""
        try:
            return await self.redis.srem(key, *values)
        except Exception as e:
            ic(f"Redis srem error: {e}")
            return 0
    
    async def smembers(self, key: str) -> set:
        """Получить все элементы множества"""
        try:
            return await self.redis.smembers(key)
        except Exception as e:
            ic(f"Redis smembers error: {e}")
            return set()
    
    async def sismember(self, key: str, value: str) -> bool:
        """Проверить наличие в множестве"""
        try:
            return await self.redis.sismember(key, value)
        except Exception as e:
            ic(f"Redis sismember error: {e}")
            return False


# Глобальный экземпляр
redis_client = RedisClient()