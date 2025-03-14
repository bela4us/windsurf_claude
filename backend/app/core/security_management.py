from typing import Dict, Any, Optional, List, Union, Type, Callable
import jwt
import bcrypt
import secrets
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from pathlib import Path
import json
import hashlib
import re
from functools import wraps
import rate_limit
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import redis
from redis import Redis
from aioredis import Redis as AsyncRedis
import time

logger = logging.getLogger(__name__)

@dataclass
class SecurityConfig:
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expires: int = 3600  # 1 sat
    password_salt_rounds: int = 12
    encryption_key: Optional[str] = None
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # 1 minuta
    max_login_attempts: int = 5
    lockout_duration: int = 300  # 5 minuta

@dataclass
class SecurityStats:
    total_checks: int = 0
    total_blocks: int = 0
    total_attacks: int = 0
    total_errors: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class SecurityManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        security_prefix: str = "security:",
        check_interval: int = 60,  # 1 minuta
        max_keys: int = 10000,
        batch_size: int = 100,
        max_attempts: int = 5,
        block_duration: int = 3600  # 1 sat
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.security_prefix = security_prefix
        self.check_interval = check_interval
        self.max_keys = max_keys
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self.block_duration = block_duration
        
        self.stats = SecurityStats()
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
                self._check_security()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def check_ip(
        self,
        ip: str
    ) -> bool:
        """Provjerava IP adresu."""
        try:
            # Generiraj ključ
            ip_key = f"{self.security_prefix}ip:{ip}"
            
            # Dohvati podatke
            ip_data = await self._redis.get(ip_key)
            if not ip_data:
                return True
                
            # Parsiraj podatke
            ip_info = json.loads(ip_data)
            
            # Provjeri blokiranje
            if ip_info["blocked_until"]:
                blocked_until = datetime.fromisoformat(ip_info["blocked_until"])
                if blocked_until > datetime.now():
                    self.stats.total_blocks += 1
                    return False
                else:
                    ip_info["blocked_until"] = None
                    ip_info["attempts"] = 0
                    
            # Ažuriraj statistiku
            self.stats.total_checks += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri provjeri IP adrese: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return True
            
    async def check_token(
        self,
        token: str
    ) -> bool:
        """Provjerava token."""
        try:
            # Generiraj ključ
            token_key = f"{self.security_prefix}token:{token}"
            
            # Provjeri postojanje
            if not await self._redis.exists(token_key):
                return False
                
            # Ažuriraj statistiku
            self.stats.total_checks += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri provjeri tokena: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def check_password(
        self,
        password: str,
        hashed_password: str
    ) -> bool:
        """Provjerava lozinku."""
        try:
            # Provjeri lozinku
            return bcrypt.checkpw(
                password.encode(),
                hashed_password.encode()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri provjeri lozinke: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def record_attempt(
        self,
        ip: str,
        success: bool
    ) -> None:
        """Bilježi pokušaj."""
        try:
            # Generiraj ključ
            ip_key = f"{self.security_prefix}ip:{ip}"
            
            # Dohvati podatke
            ip_data = await self._redis.get(ip_key)
            if not ip_data:
                ip_info = {
                    "ip": ip,
                    "attempts": 0,
                    "blocked_until": None,
                    "last_attempt": None
                }
            else:
                ip_info = json.loads(ip_data)
                
            # Ažuriraj podatke
            ip_info["attempts"] += 1
            ip_info["last_attempt"] = datetime.now().isoformat()
            
            if not success and ip_info["attempts"] >= self.max_attempts:
                ip_info["blocked_until"] = (
                    datetime.now() + timedelta(seconds=self.block_duration)
                ).isoformat()
                
            # Spremi podatke
            await self._redis.set(ip_key, json.dumps(ip_info))
            
        except Exception as e:
            self.logger.error(f"Greška pri bilježenju pokušaja: {e}")
            
    async def record_attack(
        self,
        ip: str,
        attack_type: str,
        details: Dict[str, Any] = None
    ) -> None:
        """Bilježi napad."""
        try:
            # Generiraj ključ
            attack_key = f"{self.security_prefix}attack:{ip}:{int(time.time())}"
            
            # Kreiraj podatke
            attack_data = {
                "ip": ip,
                "type": attack_type,
                "details": details or {},
                "timestamp": datetime.now().isoformat()
            }
            
            # Spremi podatke
            await self._redis.set(attack_key, json.dumps(attack_data))
            
            # Ažuriraj statistiku
            self.stats.total_attacks += 1
            
        except Exception as e:
            self.logger.error(f"Greška pri bilježenju napada: {e}")
            
    def hash_password(
        self,
        password: str
    ) -> str:
        """Hashira lozinku."""
        try:
            # Hashiraj lozinku
            return bcrypt.hashpw(
                password.encode(),
                bcrypt.gensalt()
            ).decode()
            
        except Exception as e:
            self.logger.error(f"Greška pri hashiranju lozinke: {e}")
            raise
            
    def generate_token(
        self,
        length: int = 32
    ) -> str:
        """Generira token."""
        try:
            # Generiraj token
            return secrets.token_urlsafe(length)
            
        except Exception as e:
            self.logger.error(f"Greška pri generiranju tokena: {e}")
            raise
            
    async def _check_security(self) -> None:
        """Provjerava sigurnost."""
        while True:
            try:
                # Dohvati sve ključeve
                keys = await self._redis.keys(f"{self.security_prefix}*")
                
                # Provjeri broj ključeva
                if len(keys) > self.max_keys:
                    await self._cleanup_keys()
                    
                # Čekaj sljedeći interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri provjeri sigurnosti: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _cleanup_keys(self) -> None:
        """Čisti ključeve."""
        try:
            # Dohvati sve ključeve
            keys = await self._redis.keys(f"{self.security_prefix}*")
            
            if not keys:
                return
                
            # Obriši ključeve
            await self._redis.delete(*keys)
            
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju ključeva: {e}")
            
    def get_stats(self) -> SecurityStats:
        """Dohvaća statistiku sigurnosti."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje sigurnošću."""
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
            self.logger.error(f"Greška pri zatvaranju security menadžera: {e}") 