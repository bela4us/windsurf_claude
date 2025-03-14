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
import bcrypt
import argon2
import scrypt
import pbkdf2
import passlib.hash
import crypt
import hmac
import base64
import uuid
import qrcode
import pyotp
import webauthn
import ldap
import oauthlib
import requests_oauthlib
import python_jose
import itsdangerous
import fernet
import nacl
import cryptography
from jwt import encode, decode
from bcrypt import hashpw, checkpw
from argon2 import PasswordHasher
from scrypt import hash as scrypt_hash
from pbkdf2 import crypt as pbkdf2_crypt
from passlib.hash import pbkdf2_sha256
from crypt import crypt
from hmac import new as hmac_new
from base64 import b64encode, b64decode
from uuid import uuid4
from qrcode import QRCode
from pyotp import TOTP
from webauthn import generate_registration_options
from ldap import initialize
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
class UserData:
    id: str
    username: str
    email: str
    password_hash: str
    created_at: datetime
    last_login: Optional[datetime]
    is_active: bool
    metadata: Dict[str, Any]

@dataclass
class AuthStats:
    total_logins: int = 0
    total_failures: int = 0
    total_errors: int = 0
    current_users: int = 0
    peak_users: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class AuthManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        user_prefix: str = "user:",
        check_interval: int = 60,  # 1 minuta
        max_users: int = 1000,
        max_failures: int = 5,
        block_duration: int = 3600,  # 1 sat
        batch_size: int = 100
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.user_prefix = user_prefix
        self.check_interval = check_interval
        self.max_users = max_users
        self.max_failures = max_failures
        self.block_duration = block_duration
        self.batch_size = batch_size
        
        self.stats = AuthStats()
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
                self._check_users()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def register(
        self,
        username: str,
        email: str,
        password: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[UserData]:
        """Registrira korisnika."""
        try:
            # Provjeri postojećeg korisnika
            if await self._redis.exists(f"{self.user_prefix}{username}"):
                return None
                
            # Generiraj ID
            user_id = secrets.token_urlsafe(32)
            
            # Kreiraj korisnika
            user = UserData(
                id=user_id,
                username=username,
                email=email,
                password_hash=self._hash_password(password),
                created_at=datetime.now(),
                last_login=None,
                is_active=True,
                metadata=metadata or {}
            )
            
            # Spremi korisnika
            await self._redis.set(
                f"{self.user_prefix}{username}",
                json.dumps(user.__dict__)
            )
            
            # Ažuriraj statistiku
            self.stats.current_users += 1
            if self.stats.current_users > self.stats.peak_users:
                self.stats.peak_users = self.stats.current_users
                
            return user
            
        except Exception as e:
            self.logger.error(f"Greška pri registraciji korisnika: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def login(
        self,
        username: str,
        password: str
    ) -> Optional[UserData]:
        """Prijavljuje korisnika."""
        try:
            # Dohvati korisnika
            data = await self._redis.get(f"{self.user_prefix}{username}")
            if not data:
                return None
                
            # Parsiraj korisnika
            user = UserData(**json.loads(data))
            
            # Provjeri lozinku
            if not self._verify_password(password, user.password_hash):
                await self._log_failure(username)
                return None
                
            # Provjeri blokiranje
            if not user.is_active:
                return None
                
            # Ažuriraj prijavu
            user.last_login = datetime.now()
            await self._redis.set(
                f"{self.user_prefix}{username}",
                json.dumps(user.__dict__)
            )
            
            # Ažuriraj statistiku
            self.stats.total_logins += 1
            
            return user
            
        except Exception as e:
            self.logger.error(f"Greška pri prijavi korisnika: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def update(
        self,
        username: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Ažurira korisnika."""
        try:
            # Dohvati korisnika
            data = await self._redis.get(f"{self.user_prefix}{username}")
            if not data:
                return False
                
            # Parsiraj korisnika
            user = UserData(**json.loads(data))
            
            # Ažuriraj metapodatke
            user.metadata.update(metadata)
            
            # Spremi korisnika
            await self._redis.set(
                f"{self.user_prefix}{username}",
                json.dumps(user.__dict__)
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri ažuriranju korisnika: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def delete(
        self,
        username: str
    ) -> bool:
        """Briše korisnika."""
        try:
            # Obriši korisnika
            await self._redis.delete(f"{self.user_prefix}{username}")
            
            # Ažuriraj statistiku
            self.stats.current_users -= 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri brisanju korisnika: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    def _hash_password(self, password: str) -> str:
        """Hashira lozinku."""
        salt = secrets.token_hex(16)
        return f"{salt}:{hashlib.sha256(f'{salt}{password}'.encode()).hexdigest()}"
        
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Provjerava lozinku."""
        salt, hash_value = password_hash.split(":")
        return hashlib.sha256(f'{salt}{password}'.encode()).hexdigest() == hash_value
        
    async def _log_failure(self, username: str) -> None:
        """Bilježi neuspješnu prijavu."""
        try:
            # Dohvati broj neuspjeha
            failures = await self._redis.incr(f"{self.user_prefix}{username}:failures")
            
            # Ažuriraj statistiku
            self.stats.total_failures += 1
            
            # Provjeri blokiranje
            if failures >= self.max_failures:
                # Dohvati korisnika
                data = await self._redis.get(f"{self.user_prefix}{username}")
                if data:
                    user = UserData(**json.loads(data))
                    user.is_active = False
                    await self._redis.set(
                        f"{self.user_prefix}{username}",
                        json.dumps(user.__dict__)
                    )
                    
                # Postavi blokiranje
                await self._redis.setex(
                    f"{self.user_prefix}{username}:blocked",
                    self.block_duration,
                    "1"
                )
                
        except Exception as e:
            self.logger.error(f"Greška pri bilježenju neuspjeha: {e}")
            
    async def _check_users(self) -> None:
        """Provjerava korisnike."""
        while True:
            try:
                # Dohvati sve korisnike
                users = await self._redis.keys(f"{self.user_prefix}*")
                
                # Provjeri broj korisnika
                if len(users) > self.max_users:
                    await self._cleanup_users()
                    
                # Čekaj sljedeći interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri provjeri korisnika: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _cleanup_users(self) -> None:
        """Čisti korisnike."""
        try:
            # Dohvati sve korisnike
            users = await self._redis.keys(f"{self.user_prefix}*")
            
            if not users:
                return
                
            # Obriši korisnike
            await self._redis.delete(*users)
            
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju korisnika: {e}")
            
    def get_stats(self) -> AuthStats:
        """Dohvaća statistiku autentifikacije."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje autentifikacijom."""
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
import bcrypt
import argon2
import scrypt
import pbkdf2
import passlib.hash
import crypt
import hmac
import base64
import uuid
import qrcode
import pyotp
import webauthn
import ldap
import oauthlib
import requests_oauthlib
import python_jose
import itsdangerous
import fernet
import nacl
import cryptography
from jwt import encode, decode
from bcrypt import hashpw, checkpw
from argon2 import PasswordHasher
from scrypt import hash as scrypt_hash
from pbkdf2 import crypt as pbkdf2_crypt
from passlib.hash import pbkdf2_sha256
from crypt import crypt
from hmac import new as hmac_new
from base64 import b64encode, b64decode
from uuid import uuid4
from qrcode import QRCode
from pyotp import TOTP
from webauthn import generate_registration_options
from ldap import initialize
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
class UserData:
    id: str
    username: str
    email: str
    password_hash: str
    created_at: datetime
    last_login: Optional[datetime]
    is_active: bool
    metadata: Dict[str, Any]

@dataclass
class AuthStats:
    total_logins: int = 0
    total_failures: int = 0
    total_errors: int = 0
    current_users: int = 0
    peak_users: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class AuthManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        user_prefix: str = "user:",
        check_interval: int = 60,  # 1 minuta
        max_users: int = 1000,
        max_failures: int = 5,
        block_duration: int = 3600,  # 1 sat
        batch_size: int = 100
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.user_prefix = user_prefix
        self.check_interval = check_interval
        self.max_users = max_users
        self.max_failures = max_failures
        self.block_duration = block_duration
        self.batch_size = batch_size
        
        self.stats = AuthStats()
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
                self._check_users()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def register(
        self,
        username: str,
        email: str,
        password: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[UserData]:
        """Registrira korisnika."""
        try:
            # Provjeri postojećeg korisnika
            if await self._redis.exists(f"{self.user_prefix}{username}"):
                return None
                
            # Generiraj ID
            user_id = secrets.token_urlsafe(32)
            
            # Kreiraj korisnika
            user = UserData(
                id=user_id,
                username=username,
                email=email,
                password_hash=self._hash_password(password),
                created_at=datetime.now(),
                last_login=None,
                is_active=True,
                metadata=metadata or {}
            )
            
            # Spremi korisnika
            await self._redis.set(
                f"{self.user_prefix}{username}",
                json.dumps(user.__dict__)
            )
            
            # Ažuriraj statistiku
            self.stats.current_users += 1
            if self.stats.current_users > self.stats.peak_users:
                self.stats.peak_users = self.stats.current_users
                
            return user
            
        except Exception as e:
            self.logger.error(f"Greška pri registraciji korisnika: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def login(
        self,
        username: str,
        password: str
    ) -> Optional[UserData]:
        """Prijavljuje korisnika."""
        try:
            # Dohvati korisnika
            data = await self._redis.get(f"{self.user_prefix}{username}")
            if not data:
                return None
                
            # Parsiraj korisnika
            user = UserData(**json.loads(data))
            
            # Provjeri lozinku
            if not self._verify_password(password, user.password_hash):
                await self._log_failure(username)
                return None
                
            # Provjeri blokiranje
            if not user.is_active:
                return None
                
            # Ažuriraj prijavu
            user.last_login = datetime.now()
            await self._redis.set(
                f"{self.user_prefix}{username}",
                json.dumps(user.__dict__)
            )
            
            # Ažuriraj statistiku
            self.stats.total_logins += 1
            
            return user
            
        except Exception as e:
            self.logger.error(f"Greška pri prijavi korisnika: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def update(
        self,
        username: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Ažurira korisnika."""
        try:
            # Dohvati korisnika
            data = await self._redis.get(f"{self.user_prefix}{username}")
            if not data:
                return False
                
            # Parsiraj korisnika
            user = UserData(**json.loads(data))
            
            # Ažuriraj metapodatke
            user.metadata.update(metadata)
            
            # Spremi korisnika
            await self._redis.set(
                f"{self.user_prefix}{username}",
                json.dumps(user.__dict__)
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri ažuriranju korisnika: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def delete(
        self,
        username: str
    ) -> bool:
        """Briše korisnika."""
        try:
            # Obriši korisnika
            await self._redis.delete(f"{self.user_prefix}{username}")
            
            # Ažuriraj statistiku
            self.stats.current_users -= 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri brisanju korisnika: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    def _hash_password(self, password: str) -> str:
        """Hashira lozinku."""
        salt = secrets.token_hex(16)
        return f"{salt}:{hashlib.sha256(f'{salt}{password}'.encode()).hexdigest()}"
        
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Provjerava lozinku."""
        salt, hash_value = password_hash.split(":")
        return hashlib.sha256(f'{salt}{password}'.encode()).hexdigest() == hash_value
        
    async def _log_failure(self, username: str) -> None:
        """Bilježi neuspješnu prijavu."""
        try:
            # Dohvati broj neuspjeha
            failures = await self._redis.incr(f"{self.user_prefix}{username}:failures")
            
            # Ažuriraj statistiku
            self.stats.total_failures += 1
            
            # Provjeri blokiranje
            if failures >= self.max_failures:
                # Dohvati korisnika
                data = await self._redis.get(f"{self.user_prefix}{username}")
                if data:
                    user = UserData(**json.loads(data))
                    user.is_active = False
                    await self._redis.set(
                        f"{self.user_prefix}{username}",
                        json.dumps(user.__dict__)
                    )
                    
                # Postavi blokiranje
                await self._redis.setex(
                    f"{self.user_prefix}{username}:blocked",
                    self.block_duration,
                    "1"
                )
                
        except Exception as e:
            self.logger.error(f"Greška pri bilježenju neuspjeha: {e}")
            
    async def _check_users(self) -> None:
        """Provjerava korisnike."""
        while True:
            try:
                # Dohvati sve korisnike
                users = await self._redis.keys(f"{self.user_prefix}*")
                
                # Provjeri broj korisnika
                if len(users) > self.max_users:
                    await self._cleanup_users()
                    
                # Čekaj sljedeći interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri provjeri korisnika: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _cleanup_users(self) -> None:
        """Čisti korisnike."""
        try:
            # Dohvati sve korisnike
            users = await self._redis.keys(f"{self.user_prefix}*")
            
            if not users:
                return
                
            # Obriši korisnike
            await self._redis.delete(*users)
            
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju korisnika: {e}")
            
    def get_stats(self) -> AuthStats:
        """Dohvaća statistiku autentifikacije."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje autentifikacijom."""
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
            self.logger.error(f"Greška pri zatvaranju auth menadžera: {e}") 