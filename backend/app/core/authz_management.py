<<<<<<< HEAD
from typing import Dict, Any, Optional, List, Union, Type, Callable
import logging
import asyncio
import time
import json
from datetime import datetime
from dataclasses import dataclass
from redis import Redis
from aioredis import Redis as AsyncRedis

@dataclass
class AuthzStats:
    total_roles: int = 0
    total_permissions: int = 0
    total_role_assignments: int = 0
    total_permission_checks: int = 0
    successful_permission_checks: int = 0
    failed_permission_checks: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class AuthzManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        role_prefix: str = "role:",
        permission_prefix: str = "permission:",
        cache_ttl: int = 3600,  # 1 sat
        cache_prefix: str = "cache:"
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.role_prefix = role_prefix
        self.permission_prefix = permission_prefix
        self.cache_ttl = cache_ttl
        self.cache_prefix = cache_prefix
        
        self.stats = AuthzStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Inicijalizira Redis konekciju."""
        try:
            self._redis = await AsyncRedis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def create_role(
        self,
        role_name: str,
        permissions: List[str]
    ) -> bool:
        """Kreira novu ulogu."""
        try:
            # Provjeri postoji li uloga
            role_key = f"{self.role_prefix}{role_name}"
            if await self._redis.exists(role_key):
                return False
                
            # Spremi ulogu s dozvolama
            role_data = {
                "name": role_name,
                "permissions": permissions,
                "created_at": time.time()
            }
            
            await self._redis.set(
                role_key,
                json.dumps(role_data)
            )
            
            self.stats.total_roles += 1
            self.stats.total_permissions += len(permissions)
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri kreiranju uloge: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def delete_role(
        self,
        role_name: str
    ) -> bool:
        """Briše ulogu."""
        try:
            # Provjeri postoji li uloga
            role_key = f"{self.role_prefix}{role_name}"
            if not await self._redis.exists(role_key):
                return False
                
            # Dohvati podatke uloge
            role_data = await self._redis.get(role_key)
            if not role_data:
                return False
                
            role_data = json.loads(role_data)
            
            # Obriši ulogu
            await self._redis.delete(role_key)
            
            # Očisti cache za sve korisnike s tom ulogom
            await self._clear_role_cache(role_name)
            
            self.stats.total_roles -= 1
            self.stats.total_permissions -= len(role_data["permissions"])
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri brisanju uloge: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def assign_role(
        self,
        username: str,
        role_name: str
    ) -> bool:
        """Dodjeljuje ulogu korisniku."""
        try:
            # Provjeri postoji li uloga
            role_key = f"{self.role_prefix}{role_name}"
            if not await self._redis.exists(role_key):
                return False
                
            # Dodaj ulogu korisniku
            user_roles_key = f"{self.role_prefix}user:{username}"
            await self._redis.sadd(user_roles_key, role_name)
            
            # Očisti cache za korisnika
            await self._clear_user_cache(username)
            
            self.stats.total_role_assignments += 1
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri dodjeljivanju uloge: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def revoke_role(
        self,
        username: str,
        role_name: str
    ) -> bool:
        """Oduzima ulogu korisniku."""
        try:
            # Provjeri postoji li uloga
            role_key = f"{self.role_prefix}{role_name}"
            if not await self._redis.exists(role_key):
                return False
                
            # Ukloni ulogu korisniku
            user_roles_key = f"{self.role_prefix}user:{username}"
            await self._redis.srem(user_roles_key, role_name)
            
            # Očisti cache za korisnika
            await self._clear_user_cache(username)
            
            self.stats.total_role_assignments -= 1
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri oduzimanju uloge: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def has_permission(
        self,
        username: str,
        permission: str
    ) -> bool:
        """Provjerava ima li korisnik dozvolu."""
        try:
            self.stats.total_permission_checks += 1
            
            # Provjeri cache
            cache_key = f"{self.cache_prefix}{username}:{permission}"
            cached_result = await self._redis.get(cache_key)
            if cached_result is not None:
                return cached_result == "true"
                
            # Dohvati uloge korisnika
            user_roles_key = f"{self.role_prefix}user:{username}"
            roles = await self._redis.smembers(user_roles_key)
            
            # Provjeri dozvole za svaku ulogu
            for role_name in roles:
                role_key = f"{self.role_prefix}{role_name}"
                role_data = await self._redis.get(role_key)
                if not role_data:
                    continue
                    
                role_data = json.loads(role_data)
                if permission in role_data["permissions"]:
                    # Spremi u cache
                    await self._cache_permission(username, permission, True)
                    self.stats.successful_permission_checks += 1
                    return True
                    
            # Spremi u cache
            await self._cache_permission(username, permission, False)
            self.stats.failed_permission_checks += 1
            return False
            
        except Exception as e:
            self.logger.error(f"Greška pri provjeri dozvole: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def get_user_roles(
        self,
        username: str
    ) -> List[str]:
        """Dohvaća uloge korisnika."""
        try:
            user_roles_key = f"{self.role_prefix}user:{username}"
            roles = await self._redis.smembers(user_roles_key)
            return list(roles)
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu uloga korisnika: {e}")
            return []
            
    async def get_role_permissions(
        self,
        role_name: str
    ) -> List[str]:
        """Dohvaća dozvole uloge."""
        try:
            role_key = f"{self.role_prefix}{role_name}"
            role_data = await self._redis.get(role_key)
            if not role_data:
                return []
                
            role_data = json.loads(role_data)
            return role_data["permissions"]
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu dozvola uloge: {e}")
            return []
            
    async def _cache_permission(
        self,
        username: str,
        permission: str,
        has_permission: bool
    ) -> None:
        """Sprema rezultat provjere dozvole u cache."""
        try:
            cache_key = f"{self.cache_prefix}{username}:{permission}"
            await self._redis.set(
                cache_key,
                str(has_permission).lower(),
                ex=self.cache_ttl
            )
        except Exception as e:
            self.logger.error(f"Greška pri spremanju u cache: {e}")
            
    async def _clear_user_cache(
        self,
        username: str
    ) -> None:
        """Briše cache za korisnika."""
        try:
            pattern = f"{self.cache_prefix}{username}:*"
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
        except Exception as e:
            self.logger.error(f"Greška pri brisanju cache-a korisnika: {e}")
            
    async def _clear_role_cache(
        self,
        role_name: str
    ) -> None:
        """Briše cache za ulogu."""
        try:
            pattern = f"{self.cache_prefix}*:{role_name}"
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
        except Exception as e:
            self.logger.error(f"Greška pri brisanju cache-a uloge: {e}")
            
    def get_stats(self) -> AuthzStats:
        """Dohvaća statistiku autorizacije."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje autorizacijom."""
        try:
            if self._redis:
                await self._redis.close()
        except Exception as e:
            self.logger.error(f"Greška pri zatvaranju authz menadžera: {e}") 
=======
from typing import Dict, Any, Optional, List, Union, Type, Callable
import logging
import asyncio
import time
import json
from datetime import datetime
from dataclasses import dataclass
from redis import Redis
from aioredis import Redis as AsyncRedis

@dataclass
class AuthzStats:
    total_roles: int = 0
    total_permissions: int = 0
    total_role_assignments: int = 0
    total_permission_checks: int = 0
    successful_permission_checks: int = 0
    failed_permission_checks: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class AuthzManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        role_prefix: str = "role:",
        permission_prefix: str = "permission:",
        cache_ttl: int = 3600,  # 1 sat
        cache_prefix: str = "cache:"
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.role_prefix = role_prefix
        self.permission_prefix = permission_prefix
        self.cache_ttl = cache_ttl
        self.cache_prefix = cache_prefix
        
        self.stats = AuthzStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Inicijalizira Redis konekciju."""
        try:
            self._redis = await AsyncRedis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def create_role(
        self,
        role_name: str,
        permissions: List[str]
    ) -> bool:
        """Kreira novu ulogu."""
        try:
            # Provjeri postoji li uloga
            role_key = f"{self.role_prefix}{role_name}"
            if await self._redis.exists(role_key):
                return False
                
            # Spremi ulogu s dozvolama
            role_data = {
                "name": role_name,
                "permissions": permissions,
                "created_at": time.time()
            }
            
            await self._redis.set(
                role_key,
                json.dumps(role_data)
            )
            
            self.stats.total_roles += 1
            self.stats.total_permissions += len(permissions)
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri kreiranju uloge: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def delete_role(
        self,
        role_name: str
    ) -> bool:
        """Briše ulogu."""
        try:
            # Provjeri postoji li uloga
            role_key = f"{self.role_prefix}{role_name}"
            if not await self._redis.exists(role_key):
                return False
                
            # Dohvati podatke uloge
            role_data = await self._redis.get(role_key)
            if not role_data:
                return False
                
            role_data = json.loads(role_data)
            
            # Obriši ulogu
            await self._redis.delete(role_key)
            
            # Očisti cache za sve korisnike s tom ulogom
            await self._clear_role_cache(role_name)
            
            self.stats.total_roles -= 1
            self.stats.total_permissions -= len(role_data["permissions"])
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri brisanju uloge: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def assign_role(
        self,
        username: str,
        role_name: str
    ) -> bool:
        """Dodjeljuje ulogu korisniku."""
        try:
            # Provjeri postoji li uloga
            role_key = f"{self.role_prefix}{role_name}"
            if not await self._redis.exists(role_key):
                return False
                
            # Dodaj ulogu korisniku
            user_roles_key = f"{self.role_prefix}user:{username}"
            await self._redis.sadd(user_roles_key, role_name)
            
            # Očisti cache za korisnika
            await self._clear_user_cache(username)
            
            self.stats.total_role_assignments += 1
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri dodjeljivanju uloge: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def revoke_role(
        self,
        username: str,
        role_name: str
    ) -> bool:
        """Oduzima ulogu korisniku."""
        try:
            # Provjeri postoji li uloga
            role_key = f"{self.role_prefix}{role_name}"
            if not await self._redis.exists(role_key):
                return False
                
            # Ukloni ulogu korisniku
            user_roles_key = f"{self.role_prefix}user:{username}"
            await self._redis.srem(user_roles_key, role_name)
            
            # Očisti cache za korisnika
            await self._clear_user_cache(username)
            
            self.stats.total_role_assignments -= 1
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri oduzimanju uloge: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def has_permission(
        self,
        username: str,
        permission: str
    ) -> bool:
        """Provjerava ima li korisnik dozvolu."""
        try:
            self.stats.total_permission_checks += 1
            
            # Provjeri cache
            cache_key = f"{self.cache_prefix}{username}:{permission}"
            cached_result = await self._redis.get(cache_key)
            if cached_result is not None:
                return cached_result == "true"
                
            # Dohvati uloge korisnika
            user_roles_key = f"{self.role_prefix}user:{username}"
            roles = await self._redis.smembers(user_roles_key)
            
            # Provjeri dozvole za svaku ulogu
            for role_name in roles:
                role_key = f"{self.role_prefix}{role_name}"
                role_data = await self._redis.get(role_key)
                if not role_data:
                    continue
                    
                role_data = json.loads(role_data)
                if permission in role_data["permissions"]:
                    # Spremi u cache
                    await self._cache_permission(username, permission, True)
                    self.stats.successful_permission_checks += 1
                    return True
                    
            # Spremi u cache
            await self._cache_permission(username, permission, False)
            self.stats.failed_permission_checks += 1
            return False
            
        except Exception as e:
            self.logger.error(f"Greška pri provjeri dozvole: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def get_user_roles(
        self,
        username: str
    ) -> List[str]:
        """Dohvaća uloge korisnika."""
        try:
            user_roles_key = f"{self.role_prefix}user:{username}"
            roles = await self._redis.smembers(user_roles_key)
            return list(roles)
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu uloga korisnika: {e}")
            return []
            
    async def get_role_permissions(
        self,
        role_name: str
    ) -> List[str]:
        """Dohvaća dozvole uloge."""
        try:
            role_key = f"{self.role_prefix}{role_name}"
            role_data = await self._redis.get(role_key)
            if not role_data:
                return []
                
            role_data = json.loads(role_data)
            return role_data["permissions"]
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu dozvola uloge: {e}")
            return []
            
    async def _cache_permission(
        self,
        username: str,
        permission: str,
        has_permission: bool
    ) -> None:
        """Sprema rezultat provjere dozvole u cache."""
        try:
            cache_key = f"{self.cache_prefix}{username}:{permission}"
            await self._redis.set(
                cache_key,
                str(has_permission).lower(),
                ex=self.cache_ttl
            )
        except Exception as e:
            self.logger.error(f"Greška pri spremanju u cache: {e}")
            
    async def _clear_user_cache(
        self,
        username: str
    ) -> None:
        """Briše cache za korisnika."""
        try:
            pattern = f"{self.cache_prefix}{username}:*"
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
        except Exception as e:
            self.logger.error(f"Greška pri brisanju cache-a korisnika: {e}")
            
    async def _clear_role_cache(
        self,
        role_name: str
    ) -> None:
        """Briše cache za ulogu."""
        try:
            pattern = f"{self.cache_prefix}*:{role_name}"
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
        except Exception as e:
            self.logger.error(f"Greška pri brisanju cache-a uloge: {e}")
            
    def get_stats(self) -> AuthzStats:
        """Dohvaća statistiku autorizacije."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje autorizacijom."""
        try:
            if self._redis:
                await self._redis.close()
        except Exception as e:
            self.logger.error(f"Greška pri zatvaranju authz menadžera: {e}") 
>>>>>>> c45eb88e3e23e6f6a3bf252c5a572f1c5cdb8266
            self.logger.error(f"Greška pri zatvaranju authz menadžera: {e}") 