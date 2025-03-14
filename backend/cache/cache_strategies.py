from django.core.cache import cache
from django.conf import settings
from typing import Dict, Any, Optional, List
import logging
import time
import json
from functools import wraps
import hashlib
import pickle

logger = logging.getLogger(__name__)

class CacheStrategy:
    def __init__(self):
        self.default_ttl = 300  # 5 minuta
        self.cache_prefix = "belot:"
        self.cache_version = "1.0"
        self.warmup_keys = set()

    def get_cache_key(self, key: str) -> str:
        """Generiraj cache key s prefiksom i verzijom"""
        return f"{self.cache_prefix}{self.cache_version}:{key}"

    def get(self, key: str) -> Optional[Any]:
        """Dohvati podatke iz keša"""
        try:
            cache_key = self.get_cache_key(key)
            data = cache.get(cache_key)
            
            if data is None:
                logger.debug(f"Cache miss za key: {key}")
                return None
                
            logger.debug(f"Cache hit za key: {key}")
            return pickle.loads(data)
            
        except Exception as e:
            logger.error(f"Greška pri dohvatu iz keša: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Postavi podatke u keš"""
        try:
            cache_key = self.get_cache_key(key)
            serialized_value = pickle.dumps(value)
            
            cache.set(
                cache_key,
                serialized_value,
                ttl or self.default_ttl
            )
            
            logger.debug(f"Podaci uspješno spremljeni u keš: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Greška pri spremanju u keš: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Obriši podatke iz keša"""
        try:
            cache_key = self.get_cache_key(key)
            cache.delete(cache_key)
            
            logger.debug(f"Podaci uspješno obrisani iz keša: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Greška pri brisanju iz keša: {e}")
            return False

    def delete_pattern(self, pattern: str) -> bool:
        """Obriši sve podatke koji odgovaraju patternu"""
        try:
            # Implementacija ovisi o cache backendu
            # Za Redis:
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            keys = redis_conn.keys(f"{self.cache_prefix}{pattern}")
            if keys:
                redis_conn.delete(*keys)
            
            logger.debug(f"Podaci uspješno obrisani prema patternu: {pattern}")
            return True
            
        except Exception as e:
            logger.error(f"Greška pri brisanju patterna iz keša: {e}")
            return False

    def cache_result(self, ttl: Optional[int] = None):
        """Dekorator za keširanje rezultata funkcije"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generiraj cache key
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                
                cache_key = hashlib.md5(
                    ":".join(key_parts).encode()
                ).hexdigest()
                
                # Provjeri keš
                cached_result = self.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Izvrši funkciju
                result = func(*args, **kwargs)
                
                # Spremi u keš
                self.set(cache_key, result, ttl)
                
                return result
            return wrapper
        return decorator

    def warm_cache(self, keys: List[str]):
        """Cache warming za navedene ključeve"""
        try:
            for key in keys:
                if key not in self.warmup_keys:
                    # Implementacija ovisi o tipu podataka
                    # Primjer za korisnike:
                    if key.startswith("user:"):
                        from users.models import User
                        user_id = key.split(":")[1]
                        user = User.objects.get(id=user_id)
                        self.set(key, user)
                    
                    self.warmup_keys.add(key)
                    logger.debug(f"Cache warmed za key: {key}")
                    
        except Exception as e:
            logger.error(f"Greška pri cache warmingu: {e}")

    def invalidate_cache(self, pattern: str):
        """Invalidiraj keš prema patternu"""
        try:
            self.delete_pattern(pattern)
            logger.info(f"Cache invalidiran za pattern: {pattern}")
        except Exception as e:
            logger.error(f"Greška pri invalidaciji keša: {e}")

    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Dohvati više podataka iz keša"""
        try:
            cache_keys = [self.get_cache_key(key) for key in keys]
            results = cache.get_many(cache_keys)
            
            return {
                key.replace(self.cache_prefix + self.cache_version + ":", ""): pickle.loads(value)
                for key, value in results.items()
            }
            
        except Exception as e:
            logger.error(f"Greška pri dohvatu više podataka iz keša: {e}")
            return {}

    def set_many(self, data: Dict[str, Any], ttl: Optional[int] = None):
        """Postavi više podataka u keš"""
        try:
            cache_data = {
                self.get_cache_key(key): pickle.dumps(value)
                for key, value in data.items()
            }
            
            cache.set_many(cache_data, ttl or self.default_ttl)
            logger.debug(f"Više podataka uspješno spremljeno u keš")
            
        except Exception as e:
            logger.error(f"Greška pri spremanju više podataka u keš: {e}")

# Inicijalizacija cache strategije
cache_strategy = CacheStrategy() 