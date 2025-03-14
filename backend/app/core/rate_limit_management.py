<<<<<<< HEAD
from typing import Dict, Any, Optional, List, Callable, Union, TypeVar, Generic
import os
import json
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from pathlib import Path
import hashlib
import secrets
import orjson
import time
from functools import wraps
import signal
import sys
import redis
from redis import asyncio as aioredis
import jwt
import oauthlib
import requests_oauthlib
import python_jose
import itsdangerous
import fernet
import nacl
import cryptography
from jwt import encode, decode
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
from python_jose import jwt as jose_jwt
from itsdangerous import URLSafeTimedSerializer
from fernet import Fernet
from nacl import secret
from cryptography.fernet import Fernet as CryptographyFernet
from redis import Redis
from aioredis import Redis as AsyncRedis

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class RateLimitData:
    id: str
    name: str
    max_requests: int
    window_seconds: int
    created_at: datetime
    metadata: Dict[str, Any]

@dataclass
class RateLimitStats:
    total_checks: int = 0
    total_rejections: int = 0
    total_errors: int = 0
    current_limits: int = 0
    peak_limits: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class RateLimitManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        limit_prefix: str = "limit:",
        counter_prefix: str = "counter:",
        check_interval: int = 60,  # 1 minuta
        max_limits: int = 1000,
        batch_size: int = 100
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.limit_prefix = limit_prefix
        self.counter_prefix = counter_prefix
        self.check_interval = check_interval
        self.max_limits = max_limits
        self.batch_size = batch_size
        
        self.stats = RateLimitStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        self._check_task: Optional[asyncio.Task] = None
        
    async def initialize(self) -> None:
        """Inicijalizira Redis konekciju i pokreće provjere."""
        try:
            self._redis = await AsyncRedis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Pokreni provjere
            self._check_task = asyncio.create_task(
                self._check_limits()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def create_limit(
        self,
        name: str,
        max_requests: int,
        window_seconds: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[RateLimitData]:
        """Kreira rate limit."""
        try:
            # Provjeri postojeći limit
            if await self._redis.exists(f"{self.limit_prefix}{name}"):
                return None
                
            # Generiraj ID
            limit_id = secrets.token_urlsafe(32)
            
            # Kreiraj limit
            limit = RateLimitData(
                id=limit_id,
                name=name,
                max_requests=max_requests,
                window_seconds=window_seconds,
                created_at=datetime.now(),
                metadata=metadata or {}
            )
            
            # Spremi limit
            await self._redis.set(
                f"{self.limit_prefix}{name}",
                json.dumps(limit.__dict__)
            )
            
            # Ažuriraj statistiku
            self.stats.current_limits += 1
            if self.stats.current_limits > self.stats.peak_limits:
                self.stats.peak_limits = self.stats.current_limits
                
            return limit
            
        except Exception as e:
            self.logger.error(f"Greška pri kreiranju rate limita: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def check_limit(
        self,
        name: str,
        key: str
    ) -> bool:
        """Provjerava rate limit."""
        try:
            # Dohvati limit
            data = await self._redis.get(f"{self.limit_prefix}{name}")
            if not data:
                return True
                
            # Parsiraj limit
            limit = RateLimitData(**json.loads(data))
            
            # Dohvati brojač
            counter = await self._redis.get(
                f"{self.counter_prefix}{name}:{key}"
            )
            if not counter:
                # Postavi brojač
                await self._redis.setex(
                    f"{self.counter_prefix}{name}:{key}",
                    limit.window_seconds,
                    "1"
                )
                self.stats.total_checks += 1
                return True
                
            # Provjeri limit
            if int(counter) >= limit.max_requests:
                self.stats.total_rejections += 1
                return False
                
            # Povećaj brojač
            await self._redis.incr(
                f"{self.counter_prefix}{name}:{key}"
            )
            
            self.stats.total_checks += 1
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri provjeri rate limita: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return True
            
    async def get_limit(
        self,
        name: str
    ) -> Optional[RateLimitData]:
        """Dohvaća rate limit."""
        try:
            # Dohvati limit
            data = await self._redis.get(f"{self.limit_prefix}{name}")
            if not data:
                return None
                
            # Parsiraj limit
            return RateLimitData(**json.loads(data))
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu rate limita: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def get_limit_stats(
        self,
        name: str
    ) -> Dict[str, Any]:
        """Dohvaća statistiku rate limita."""
        try:
            # Dohvati limit
            limit = await self.get_limit(name)
            if not limit:
                return {}
                
            # Dohvati brojače
            counters = await self._redis.keys(f"{self.counter_prefix}{name}:*")
            
            return {
                "limit": limit.__dict__,
                "total_counters": len(counters)
            }
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu statistike rate limita: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return {}
            
    async def _check_limits(self) -> None:
        """Provjerava rate limite."""
        while True:
            try:
                # Dohvati sve limite
                limits = await self._redis.keys(f"{self.limit_prefix}*")
                
                # Provjeri broj limita
                if len(limits) > self.max_limits:
                    await self._cleanup_limits()
                    
                # Čekaj sljedeći interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri provjeri rate limita: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _cleanup_limits(self) -> None:
        """Čisti rate limite."""
        try:
            # Dohvati sve limite
            limits = await self._redis.keys(f"{self.limit_prefix}*")
            
            if not limits:
                return
                
            # Obriši limite
            await self._redis.delete(*limits)
            
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju rate limita: {e}")
            
    def get_stats(self) -> RateLimitStats:
        """Dohvaća statistiku rate limita."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje rate limitima."""
        try:
            # Zaustavi provjere
            if self._check_task:
                self._check_task.cancel()
                try:
                    await self._check_task
                except asyncio.CancelledError:
                    pass
                    
            # Zatvori Redis
            if self._redis:
                await self._redis.close()
                
        except Exception as e:
=======
from typing import Dict, Any, Optional, List, Callable, Union, TypeVar, Generic
import os
import json
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from pathlib import Path
import hashlib
import secrets
import orjson
import time
from functools import wraps
import signal
import sys
import redis
from redis import asyncio as aioredis
import jwt
import oauthlib
import requests_oauthlib
import python_jose
import itsdangerous
import fernet
import nacl
import cryptography
from jwt import encode, decode
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
from python_jose import jwt as jose_jwt
from itsdangerous import URLSafeTimedSerializer
from fernet import Fernet
from nacl import secret
from cryptography.fernet import Fernet as CryptographyFernet
from redis import Redis
from aioredis import Redis as AsyncRedis

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class RateLimitData:
    id: str
    name: str
    max_requests: int
    window_seconds: int
    created_at: datetime
    metadata: Dict[str, Any]

@dataclass
class RateLimitStats:
    total_checks: int = 0
    total_rejections: int = 0
    total_errors: int = 0
    current_limits: int = 0
    peak_limits: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class RateLimitManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        limit_prefix: str = "limit:",
        counter_prefix: str = "counter:",
        check_interval: int = 60,  # 1 minuta
        max_limits: int = 1000,
        batch_size: int = 100
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.limit_prefix = limit_prefix
        self.counter_prefix = counter_prefix
        self.check_interval = check_interval
        self.max_limits = max_limits
        self.batch_size = batch_size
        
        self.stats = RateLimitStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        self._check_task: Optional[asyncio.Task] = None
        
    async def initialize(self) -> None:
        """Inicijalizira Redis konekciju i pokreće provjere."""
        try:
            self._redis = await AsyncRedis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Pokreni provjere
            self._check_task = asyncio.create_task(
                self._check_limits()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def create_limit(
        self,
        name: str,
        max_requests: int,
        window_seconds: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[RateLimitData]:
        """Kreira rate limit."""
        try:
            # Provjeri postojeći limit
            if await self._redis.exists(f"{self.limit_prefix}{name}"):
                return None
                
            # Generiraj ID
            limit_id = secrets.token_urlsafe(32)
            
            # Kreiraj limit
            limit = RateLimitData(
                id=limit_id,
                name=name,
                max_requests=max_requests,
                window_seconds=window_seconds,
                created_at=datetime.now(),
                metadata=metadata or {}
            )
            
            # Spremi limit
            await self._redis.set(
                f"{self.limit_prefix}{name}",
                json.dumps(limit.__dict__)
            )
            
            # Ažuriraj statistiku
            self.stats.current_limits += 1
            if self.stats.current_limits > self.stats.peak_limits:
                self.stats.peak_limits = self.stats.current_limits
                
            return limit
            
        except Exception as e:
            self.logger.error(f"Greška pri kreiranju rate limita: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def check_limit(
        self,
        name: str,
        key: str
    ) -> bool:
        """Provjerava rate limit."""
        try:
            # Dohvati limit
            data = await self._redis.get(f"{self.limit_prefix}{name}")
            if not data:
                return True
                
            # Parsiraj limit
            limit = RateLimitData(**json.loads(data))
            
            # Dohvati brojač
            counter = await self._redis.get(
                f"{self.counter_prefix}{name}:{key}"
            )
            if not counter:
                # Postavi brojač
                await self._redis.setex(
                    f"{self.counter_prefix}{name}:{key}",
                    limit.window_seconds,
                    "1"
                )
                self.stats.total_checks += 1
                return True
                
            # Provjeri limit
            if int(counter) >= limit.max_requests:
                self.stats.total_rejections += 1
                return False
                
            # Povećaj brojač
            await self._redis.incr(
                f"{self.counter_prefix}{name}:{key}"
            )
            
            self.stats.total_checks += 1
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri provjeri rate limita: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return True
            
    async def get_limit(
        self,
        name: str
    ) -> Optional[RateLimitData]:
        """Dohvaća rate limit."""
        try:
            # Dohvati limit
            data = await self._redis.get(f"{self.limit_prefix}{name}")
            if not data:
                return None
                
            # Parsiraj limit
            return RateLimitData(**json.loads(data))
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu rate limita: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def get_limit_stats(
        self,
        name: str
    ) -> Dict[str, Any]:
        """Dohvaća statistiku rate limita."""
        try:
            # Dohvati limit
            limit = await self.get_limit(name)
            if not limit:
                return {}
                
            # Dohvati brojače
            counters = await self._redis.keys(f"{self.counter_prefix}{name}:*")
            
            return {
                "limit": limit.__dict__,
                "total_counters": len(counters)
            }
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu statistike rate limita: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return {}
            
    async def _check_limits(self) -> None:
        """Provjerava rate limite."""
        while True:
            try:
                # Dohvati sve limite
                limits = await self._redis.keys(f"{self.limit_prefix}*")
                
                # Provjeri broj limita
                if len(limits) > self.max_limits:
                    await self._cleanup_limits()
                    
                # Čekaj sljedeći interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri provjeri rate limita: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _cleanup_limits(self) -> None:
        """Čisti rate limite."""
        try:
            # Dohvati sve limite
            limits = await self._redis.keys(f"{self.limit_prefix}*")
            
            if not limits:
                return
                
            # Obriši limite
            await self._redis.delete(*limits)
            
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju rate limita: {e}")
            
    def get_stats(self) -> RateLimitStats:
        """Dohvaća statistiku rate limita."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje rate limitima."""
        try:
            # Zaustavi provjere
            if self._check_task:
                self._check_task.cancel()
                try:
                    await self._check_task
                except asyncio.CancelledError:
                    pass
                    
            # Zatvori Redis
            if self._redis:
                await self._redis.close()
                
        except Exception as e:
>>>>>>> c45eb88e3e23e6f6a3bf252c5a572f1c5cdb8266
            self.logger.error(f"Greška pri zatvaranju rate limit menadžera: {e}") 