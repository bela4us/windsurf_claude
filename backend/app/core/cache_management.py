from typing import Any, Dict, Optional, Union, List, Callable, Type
import redis
import pickle
import logging
from datetime import datetime, timedelta
import hashlib
import json
from functools import wraps
import asyncio
from dataclasses import dataclass
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import secrets
from redis import Redis
from aioredis import Redis as AsyncRedis
import time

logger = logging.getLogger(__name__)

@dataclass
class CacheStats:
    total_keys: int = 0
    total_bytes: int = 0
    total_hits: int = 0
    total_misses: int = 0
    total_evictions: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class CacheManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        cache_prefix: str = "cache:",
        max_size: int = 1024 * 1024 * 1024,  # 1 GB
        max_keys: int = 10000,
        default_ttl: int = 3600,  # 1 sat
        compression_threshold: int = 1024 * 1024,  # 1 MB
        batch_size: int = 100,
        processing_interval: int = 60,  # 1 minuta
        eviction_policy: str = "lru"  # lru, lfu, random
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.cache_prefix = cache_prefix
        self.max_size = max_size
        self.max_keys = max_keys
        self.default_ttl = default_ttl
        self.compression_threshold = compression_threshold
        self.batch_size = batch_size
        self.processing_interval = processing_interval
        self.eviction_policy = eviction_policy
        
        self.stats = CacheStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        self._processing_task: Optional[asyncio.Task] = None
        
    async def initialize(self) -> None:
        """Inicijalizira Redis konekciju i pokreće procesiranje."""
        try:
            self._redis = await AsyncRedis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Pokreni procesiranje
            self._processing_task = asyncio.create_task(
                self._process_cache()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def get(
        self,
        key: str,
        default: Any = None
    ) -> Any:
        """Dohvaća vrijednost iz keša."""
        try:
            # Generiraj ključ
            cache_key = f"{self.cache_prefix}{key}"
            
            # Dohvati vrijednost
            value = await self._redis.get(cache_key)
            
            if value is None:
                # Ažuriraj statistiku
                self.stats.total_misses += 1
                return default
                
            # Parsiraj vrijednost
            try:
                data = json.loads(value)
            except json.JSONDecodeError:
                data = pickle.loads(value.encode())
                
            # Ažuriraj statistiku
            self.stats.total_hits += 1
            
            return data
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu iz keša: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return default
            
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Postavlja vrijednost u keš."""
        try:
            # Generiraj ključ
            cache_key = f"{self.cache_prefix}{key}"
            
            # Serijaliziraj vrijednost
            try:
                data = json.dumps(value)
            except (TypeError, ValueError):
                data = pickle.dumps(value).decode()
                
            # Provjeri veličinu
            if len(data) > self.max_size:
                self.logger.warning(f"Vrijednost prevelika za keš: {key}")
                return False
                
            # Spremi vrijednost
            await self._redis.set(
                cache_key,
                data,
                ex=ttl or self.default_ttl
            )
            
            # Ažuriraj statistiku
            self.stats.total_keys += 1
            self.stats.total_bytes += len(data)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri postavljanju u keš: {e}")
            return False
            
    async def delete(
        self,
        key: str
    ) -> bool:
        """Briše vrijednost iz keša."""
        try:
            # Generiraj ključ
            cache_key = f"{self.cache_prefix}{key}"
            
            # Obriši vrijednost
            await self._redis.delete(cache_key)
            
            # Ažuriraj statistiku
            self.stats.total_keys -= 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri brisanju iz keša: {e}")
            return False
            
    async def clear(self) -> bool:
        """Briše sve vrijednosti iz keša."""
        try:
            # Dohvati sve ključeve
            keys = await self._redis.keys(f"{self.cache_prefix}*")
            
            if not keys:
                return True
                
            # Obriši sve vrijednosti
            await self._redis.delete(*keys)
            
            # Ažuriraj statistiku
            self.stats.total_keys = 0
            self.stats.total_bytes = 0
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju keša: {e}")
            return False
            
    async def get_or_set(
        self,
        key: str,
        callback: Callable,
        ttl: Optional[int] = None
    ) -> Any:
        """Dohvaća vrijednost iz keša ili je postavlja."""
        try:
            # Pokušaj dohvatiti iz keša
            value = await self.get(key)
            if value is not None:
                return value
                
            # Izvrši callback
            value = await callback()
            
            # Spremi u keš
            await self.set(key, value, ttl)
            
            return value
            
        except Exception as e:
            self.logger.error(f"Greška pri get_or_set: {e}")
            return await callback()
            
    async def _process_cache(self) -> None:
        """Procesira keš."""
        while True:
            try:
                # Dohvati sve ključeve
                keys = await self._redis.keys(f"{self.cache_prefix}*")
                
                # Provjeri broj ključeva
                if len(keys) > self.max_keys:
                    await self._evict_keys()
                    
                # Provjeri veličinu
                total_size = await self._get_total_size()
                if total_size > self.max_size:
                    await self._evict_keys()
                    
                # Čekaj sljedeći interval
                await asyncio.sleep(self.processing_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri procesiranju keša: {e}")
                await asyncio.sleep(self.processing_interval)
                
    async def _get_total_size(self) -> int:
        """Dohvaća ukupnu veličinu keša."""
        try:
            # Dohvati sve ključeve
            keys = await self._redis.keys(f"{self.cache_prefix}*")
            
            if not keys:
                return 0
                
            # Dohvati sve vrijednosti
            values = await self._redis.mget(keys)
            
            # Izračunaj ukupnu veličinu
            total_size = sum(len(v) for v in values if v)
            
            return total_size
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu ukupne veličine: {e}")
            return 0
            
    async def _evict_keys(self) -> None:
        """Briše ključeve prema politici."""
        try:
            # Dohvati sve ključeve
            keys = await self._redis.keys(f"{self.cache_prefix}*")
            
            if not keys:
                return
                
            if self.eviction_policy == "lru":
                # Dohvati najstarije ključeve
                keys_to_evict = keys[:self.batch_size]
            elif self.eviction_policy == "lfu":
                # Dohvati najmanje korištene ključeve
                keys_to_evict = keys[:self.batch_size]
            else:  # random
                # Dohvati nasumične ključeve
                keys_to_evict = keys[:self.batch_size]
                
            # Obriši ključeve
            await self._redis.delete(*keys_to_evict)
            
            # Ažuriraj statistiku
            self.stats.total_keys -= len(keys_to_evict)
            self.stats.total_evictions += len(keys_to_evict)
            
        except Exception as e:
            self.logger.error(f"Greška pri brisanju ključeva: {e}")
            
    def get_stats(self) -> CacheStats:
        """Dohvaća statistiku keša."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje kešom."""
        try:
            # Zaustavi procesiranje
            if self._processing_task:
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass
                    
            # Zatvori Redis
            if self._redis:
                await self._redis.close()
                
        except Exception as e:
            self.logger.error(f"Greška pri zatvaranju cache menadžera: {e}")

    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Dohvaća više vrijednosti iz cache-a."""
        try:
            full_keys = [self._get_full_key(key) for key in keys]
            values = self.redis.mget(full_keys)
            
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    result[key] = self._deserialize(value)
                    
            return result
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu više vrijednosti iz cache-a: {e}")
            return {}
            
    def set_many(
        self,
        mapping: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Postavlja više vrijednosti u cache."""
        try:
            if ttl is None:
                ttl = self.default_ttl
                
            pipeline = self.redis.pipeline()
            for key, value in mapping.items():
                full_key = self._get_full_key(key)
                serialized_value = self._serialize(value)
                pipeline.set(full_key, serialized_value, ex=ttl)
                
            pipeline.execute()
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri postavljanju više vrijednosti u cache: {e}")
            return False
            
    def delete_many(self, keys: List[str]) -> bool:
        """Briše više vrijednosti iz cache-a."""
        try:
            full_keys = [self._get_full_key(key) for key in keys]
            return bool(self.redis.delete(*full_keys))
            
        except Exception as e:
            self.logger.error(f"Greška pri brisanju više vrijednosti iz cache-a: {e}")
            return False
            
    def _get_full_key(self, key: str) -> str:
        """Generira puni ključ za cache."""
        return f"{self.cache_prefix}{key}"
        
    def _serialize(self, value: Any) -> str:
        """Serijalizira vrijednost za spremanje u cache."""
        try:
            return json.dumps(value)
        except:
            return pickle.dumps(value)
            
    def _deserialize(self, value: str) -> Any:
        """Deserijalizira vrijednost iz cache-a."""
        try:
            return json.loads(value)
        except:
            return pickle.loads(value)
            
    def cached(
        self,
        ttl: Optional[int] = None,
        key_prefix: Optional[str] = None
    ):
        """Dekorator za cache-iranje rezultata funkcije."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if key_prefix:
                    key = f"{key_prefix}:{self._generate_key(func, args, kwargs)}"
                else:
                    key = self._generate_key(func, args, kwargs)
                    
                value = self.get(key)
                if value is None:
                    value = func(*args, **kwargs)
                    self.set(key, value, ttl)
                return value
            return wrapper
        return decorator
        
    def _generate_key(self, func, args, kwargs) -> str:
        """Generira jedinstveni ključ za funkciju i argumente."""
        key_parts = [func.__name__]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
        
    def cleanup(self) -> None:
        """Čisti cache i ažurira statistiku."""
        try:
            self.clear()
            self.stats.last_cleanup = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju cache-a: {e}")
            
    def monitor(self) -> Dict[str, Any]:
        """Praći stanje cache-a."""
        try:
            info = self.redis.info()
            return {
                "memory_usage": info["used_memory"],
                "hit_rate": self.stats.total_hits / (self.stats.total_hits + self.stats.total_misses) if (self.stats.total_hits + self.stats.total_misses) > 0 else 0,
                "eviction_rate": self.stats.total_evictions,
                "last_cleanup": self.stats.last_cleanup,
                "total_keys": self.redis.dbsize()
            }
            
        except Exception as e:
            self.logger.error(f"Greška pri praćenju cache-a: {e}")
            return {}
            
    def shutdown(self) -> None:
        """Zaustavlja upravljanje cache-om."""
        try:
            self.redis.close()
        except Exception as e:
            self.logger.error(f"Greška pri zatvaranju cache-a: {e}") 