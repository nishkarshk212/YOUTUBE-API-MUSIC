import json
import time
from typing import Optional, Any
from app.config import settings
from app.logger import logger

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class CacheBackend:
    """Cache backend interface."""
    
    async def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError
    
    async def set(self, key: str, value: Any, ttl: int) -> None:
        raise NotImplementedError
    
    async def delete(self, key: str) -> None:
        raise NotImplementedError
    
    async def clear(self) -> None:
        raise NotImplementedError


class MemoryCache(CacheBackend):
    """In-memory cache implementation."""
    
    def __init__(self):
        self._cache: dict = {}
        self._timestamps: dict = {}
    
    async def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            # Check if expired
            if time.time() - self._timestamps[key] > settings.cache_ttl_seconds:
                await self.delete(key)
                return None
            return self._cache[key]
        return None
    
    async def set(self, key: str, value: Any, ttl: int) -> None:
        self._cache[key] = value
        self._timestamps[key] = time.time()
    
    async def delete(self, key: str) -> None:
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)
    
    async def clear(self) -> None:
        self._cache.clear()
        self._timestamps.clear()


class RedisCache(CacheBackend):
    """Redis cache implementation."""
    
    def __init__(self):
        if not REDIS_AVAILABLE:
            raise ImportError("redis package is required for Redis cache")
        self._client = redis.from_url(settings.redis_url)
    
    async def get(self, key: str) -> Optional[Any]:
        try:
            value = self._client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            self._client.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.error(f"Redis set error: {e}")
    
    async def delete(self, key: str) -> None:
        try:
            self._client.delete(key)
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
    
    async def clear(self) -> None:
        try:
            self._client.flushdb()
        except Exception as e:
            logger.error(f"Redis clear error: {e}")


def get_cache() -> Optional[CacheBackend]:
    """Get cache backend based on configuration."""
    if not settings.cache_enabled:
        return None
    
    if settings.cache_type == "redis":
        try:
            return RedisCache()
        except Exception as e:
            logger.warning(f"Failed to initialize Redis cache, falling back to memory: {e}")
            return MemoryCache()
    
    return MemoryCache()


cache = get_cache()
