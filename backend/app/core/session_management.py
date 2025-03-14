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
class SessionData:
    id: str
    user_id: str
    data: Dict[str, Any]
    created_at: datetime
    expires_at: datetime

@dataclass
class SessionStats:
    total_sessions: int = 0
    total_expired: int = 0
    total_errors: int = 0
    current_sessions: int = 0
    peak_sessions: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class SessionManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        session_prefix: str = "session:",
        check_interval: int = 60,  # 1 minuta
        max_sessions: int = 1000,
        session_ttl: int = 3600,  # 1 sat
        batch_size: int = 100
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.session_prefix = session_prefix
        self.check_interval = check_interval
        self.max_sessions = max_sessions
        self.session_ttl = session_ttl
        self.batch_size = batch_size
        
        self.stats = SessionStats()
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
                self._check_sessions()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def create_session(
        self,
        user_id: str,
        data: Dict[str, Any] = None
    ) -> Optional[SessionData]:
        """Kreira novu sesiju."""
        try:
            # Generiraj ID
            session_id = secrets.token_urlsafe(32)
            
            # Kreiraj sesiju
            session = SessionData(
                id=session_id,
                user_id=user_id,
                data=data or {},
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=self.session_ttl)
            )
            
            # Spremi sesiju
            await self._redis.setex(
                f"{self.session_prefix}{session_id}",
                self.session_ttl,
                json.dumps(session.__dict__)
            )
            
            # Ažuriraj statistiku
            self.stats.total_sessions += 1
            self.stats.current_sessions += 1
            if self.stats.current_sessions > self.stats.peak_sessions:
                self.stats.peak_sessions = self.stats.current_sessions
                
            return session
            
        except Exception as e:
            self.logger.error(f"Greška pri kreiranju sesije: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def get_session(
        self,
        session_id: str
    ) -> Optional[SessionData]:
        """Dohvaća podatke sesije."""
        try:
            # Dohvati podatke
            data = await self._redis.get(f"{self.session_prefix}{session_id}")
            if not data:
                return None
                
            # Parsiraj podatke
            session = SessionData(**json.loads(data))
            
            # Provjeri istek
            if session.expires_at < datetime.now():
                await self.delete_session(session_id)
                self.stats.total_expired += 1
                return None
                
            return session
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu sesije: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def update_session(
        self,
        session_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """Ažurira podatke sesije."""
        try:
            # Dohvati sesiju
            session = await self.get_session(session_id)
            if not session:
                return False
                
            # Ažuriraj podatke
            session.data.update(data)
            session.expires_at = datetime.now() + timedelta(seconds=self.session_ttl)
            
            # Spremi sesiju
            await self._redis.setex(
                f"{self.session_prefix}{session_id}",
                self.session_ttl,
                json.dumps(session.__dict__)
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri ažuriranju sesije: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def delete_session(
        self,
        session_id: str
    ) -> bool:
        """Briše sesiju."""
        try:
            # Obriši sesiju
            await self._redis.delete(f"{self.session_prefix}{session_id}")
            
            # Ažuriraj statistiku
            self.stats.current_sessions -= 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri brisanju sesije: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def _check_sessions(self) -> None:
        """Provjerava sesije."""
        while True:
            try:
                # Dohvati sve ključeve
                keys = await self._redis.keys(f"{self.session_prefix}*")
                
                # Provjeri broj sesija
                if len(keys) > self.max_sessions:
                    await self._cleanup_sessions()
                    
                # Čekaj sljedeći interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri provjeri sesija: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _cleanup_sessions(self) -> None:
        """Čisti sesije."""
        try:
            # Dohvati sve ključeve
            keys = await self._redis.keys(f"{self.session_prefix}*")
            
            if not keys:
                return
                
            # Obriši ključeve
            await self._redis.delete(*keys)
            
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju sesija: {e}")
            
    def get_stats(self) -> SessionStats:
        """Dohvaća statistiku sesija."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje sesijama."""
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
            self.logger.error(f"Greška pri zatvaranju session menadžera: {e}") 