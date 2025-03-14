from django.core.cache import cache
from django.conf import settings
import redis
import json
import logging
from typing import Any, Optional, List, Dict
from functools import wraps
import time

logger = logging.getLogger(__name__)

class RedisCacheManager:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        self.default_timeout = 3600  # 1 sat
        self._cache_prefix = "belot:"

    def _get_key(self, key: str) -> str:
        """Dodaje prefix za namespace"""
        return f"{self._cache_prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        """Dohvaća vrijednost iz cache-a"""
        try:
            value = self.redis_client.get(self._get_key(key))
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Greška pri dohvatu iz cache-a: {e}")
            return None

    def set(self, key: str, value: Any, timeout: int = None) -> bool:
        """Postavlja vrijednost u cache"""
        try:
            key = self._get_key(key)
            value = json.dumps(value)
            return self.redis_client.setex(
                key,
                timeout or self.default_timeout,
                value
            )
        except Exception as e:
            logger.error(f"Greška pri postavljanju u cache: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Briše vrijednost iz cache-a"""
        try:
            return bool(self.redis_client.delete(self._get_key(key)))
        except Exception as e:
            logger.error(f"Greška pri brisanju iz cache-a: {e}")
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        """Briše sve ključeve koji odgovaraju patternu"""
        try:
            keys = self.redis_client.keys(self._get_key(pattern))
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Greška pri invalidaciji patterna: {e}")
            return 0

    def get_or_set(self, key: str, default: Any, timeout: int = None) -> Any:
        """Dohvaća vrijednost ili postavlja default ako ne postoji"""
        value = self.get(key)
        if value is None:
            value = default
            self.set(key, value, timeout)
        return value

    def cache_key(self, timeout: int = None):
        """Dekorator za cache-anje funkcija"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generiraj jedinstveni ključ za funkciju i argumente
                key_parts = [func.__name__]
                key_parts.extend([str(arg) for arg in args])
                key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
                cache_key = ":".join(key_parts)

                # Pokušaj dohvatiti iz cache-a
                result = self.get(cache_key)
                if result is not None:
                    return result

                # Ako nije u cache-u, izvrši funkciju i spremi rezultat
                result = func(*args, **kwargs)
                self.set(cache_key, result, timeout)
                return result
            return wrapper
        return decorator

    def invalidate_related(self, key_patterns: List[str]) -> None:
        """Invalidira sve povezane cache ključeve"""
        for pattern in key_patterns:
            self.invalidate_pattern(pattern)

    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Dohvaća više vrijednosti odjednom"""
        try:
            prefixed_keys = [self._get_key(key) for key in keys]
            values = self.redis_client.mget(prefixed_keys)
            return {
                key: json.loads(value) if value else None
                for key, value in zip(keys, values)
            }
        except Exception as e:
            logger.error(f"Greška pri dohvatu više vrijednosti: {e}")
            return {}

    def set_many(self, data: Dict[str, Any], timeout: int = None) -> bool:
        """Postavlja više vrijednosti odjednom"""
        try:
            pipeline = self.redis_client.pipeline()
            for key, value in data.items():
                key = self._get_key(key)
                value = json.dumps(value)
                pipeline.setex(key, timeout or self.default_timeout, value)
            return pipeline.execute()
        except Exception as e:
            logger.error(f"Greška pri postavljanju više vrijednosti: {e}")
            return False

# Singleton instanca
cache_manager = RedisCacheManager() 