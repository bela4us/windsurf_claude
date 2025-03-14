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
class RoleData:
    id: str
    name: str
    permissions: List[str]
    created_at: datetime
    metadata: Dict[str, Any]

@dataclass
class UserRoleData:
    user_id: str
    role_id: str
    assigned_at: datetime
    metadata: Dict[str, Any]

@dataclass
class AuthzStats:
    total_checks: int = 0
    total_rejections: int = 0
    total_errors: int = 0
    current_roles: int = 0
    peak_roles: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class AuthorizationManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        role_prefix: str = "role:",
        user_role_prefix: str = "user_role:",
        check_interval: int = 60,  # 1 minuta
        max_roles: int = 1000,
        batch_size: int = 100
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.role_prefix = role_prefix
        self.user_role_prefix = user_role_prefix
        self.check_interval = check_interval
        self.max_roles = max_roles
        self.batch_size = batch_size
        
        self.stats = AuthzStats()
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
                self._check_roles()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def create_role(
        self,
        name: str,
        permissions: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[RoleData]:
        """Kreira ulogu."""
        try:
            # Provjeri postojeću ulogu
            if await self._redis.exists(f"{self.role_prefix}{name}"):
                return None
                
            # Generiraj ID
            role_id = secrets.token_urlsafe(32)
            
            # Kreiraj ulogu
            role = RoleData(
                id=role_id,
                name=name,
                permissions=permissions,
                created_at=datetime.now(),
                metadata=metadata or {}
            )
            
            # Spremi ulogu
            await self._redis.set(
                f"{self.role_prefix}{name}",
                json.dumps(role.__dict__)
            )
            
            # Ažuriraj statistiku
            self.stats.current_roles += 1
            if self.stats.current_roles > self.stats.peak_roles:
                self.stats.peak_roles = self.stats.current_roles
                
            return role
            
        except Exception as e:
            self.logger.error(f"Greška pri kreiranju uloge: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def assign_role(
        self,
        user_id: str,
        role_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Dodjeljuje ulogu korisniku."""
        try:
            # Dohvati ulogu
            data = await self._redis.get(f"{self.role_prefix}{role_name}")
            if not data:
                return False
                
            # Parsiraj ulogu
            role = RoleData(**json.loads(data))
            
            # Kreiraj dodjelu
            user_role = UserRoleData(
                user_id=user_id,
                role_id=role.id,
                assigned_at=datetime.now(),
                metadata=metadata or {}
            )
            
            # Spremi dodjelu
            await self._redis.sadd(
                f"{self.user_role_prefix}{user_id}",
                role_name
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri dodjeli uloge: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def remove_role(
        self,
        user_id: str,
        role_name: str
    ) -> bool:
        """Uklanja ulogu korisniku."""
        try:
            # Ukloni dodjelu
            await self._redis.srem(
                f"{self.user_role_prefix}{user_id}",
                role_name
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri uklanjanju uloge: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def check_permission(
        self,
        user_id: str,
        permission: str
    ) -> bool:
        """Provjerava ima li korisnik dozvolu."""
        try:
            # Dohvati uloge
            roles = await self._redis.smembers(f"{self.user_role_prefix}{user_id}")
            if not roles:
                self.stats.total_rejections += 1
                return False
                
            # Provjeri dozvole
            for role_name in roles:
                data = await self._redis.get(f"{self.role_prefix}{role_name}")
                if data:
                    role = RoleData(**json.loads(data))
                    if permission in role.permissions:
                        self.stats.total_checks += 1
                        return True
                        
            self.stats.total_rejections += 1
            return False
            
        except Exception as e:
            self.logger.error(f"Greška pri provjeri dozvole: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def get_user_roles(
        self,
        user_id: str
    ) -> List[str]:
        """Dohvaća uloge korisnika."""
        try:
            # Dohvati uloge
            roles = await self._redis.smembers(f"{self.user_role_prefix}{user_id}")
            return list(roles)
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu uloga: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return []
            
    async def _check_roles(self) -> None:
        """Provjerava uloge."""
        while True:
            try:
                # Dohvati sve uloge
                roles = await self._redis.keys(f"{self.role_prefix}*")
                
                # Provjeri broj uloga
                if len(roles) > self.max_roles:
                    await self._cleanup_roles()
                    
                # Čekaj sljedeći interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri provjeri uloga: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _cleanup_roles(self) -> None:
        """Čisti uloge."""
        try:
            # Dohvati sve uloge
            roles = await self._redis.keys(f"{self.role_prefix}*")
            
            if not roles:
                return
                
            # Obriši uloge
            await self._redis.delete(*roles)
            
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju uloga: {e}")
            
    def get_stats(self) -> AuthzStats:
        """Dohvaća statistiku autorizacije."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje autorizacijom."""
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
            self.logger.error(f"Greška pri zatvaranju authz menadžera: {e}") 