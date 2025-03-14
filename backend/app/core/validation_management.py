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
class ValidationRuleData:
    id: str
    name: str
    schema: Dict[str, Any]
    created_at: datetime
    metadata: Dict[str, Any]

@dataclass
class ValidationStats:
    total_validations: int = 0
    total_failures: int = 0
    total_errors: int = 0
    current_rules: int = 0
    peak_rules: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class ValidationManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        rule_prefix: str = "rule:",
        check_interval: int = 60,  # 1 minuta
        max_rules: int = 1000,
        batch_size: int = 100
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.rule_prefix = rule_prefix
        self.check_interval = check_interval
        self.max_rules = max_rules
        self.batch_size = batch_size
        
        self.stats = ValidationStats()
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
                self._check_rules()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def create_rule(
        self,
        name: str,
        schema: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ValidationRuleData]:
        """Kreira pravilo validacije."""
        try:
            # Provjeri postojeće pravilo
            if await self._redis.exists(f"{self.rule_prefix}{name}"):
                return None
                
            # Generiraj ID
            rule_id = secrets.token_urlsafe(32)
            
            # Kreiraj pravilo
            rule = ValidationRuleData(
                id=rule_id,
                name=name,
                schema=schema,
                created_at=datetime.now(),
                metadata=metadata or {}
            )
            
            # Spremi pravilo
            await self._redis.set(
                f"{self.rule_prefix}{name}",
                json.dumps(rule.__dict__)
            )
            
            # Ažuriraj statistiku
            self.stats.current_rules += 1
            if self.stats.current_rules > self.stats.peak_rules:
                self.stats.peak_rules = self.stats.current_rules
                
            return rule
            
        except Exception as e:
            self.logger.error(f"Greška pri kreiranju pravila validacije: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def validate(
        self,
        name: str,
        data: Dict[str, Any]
    ) -> bool:
        """Validira podatke prema pravilu."""
        try:
            # Dohvati pravilo
            rule_data = await self._redis.get(f"{self.rule_prefix}{name}")
            if not rule_data:
                return False
                
            # Parsiraj pravilo
            rule = ValidationRuleData(**json.loads(rule_data))
            
            # Validiraj podatke
            if not self._validate_data(data, rule.schema):
                self.stats.total_failures += 1
                return False
                
            self.stats.total_validations += 1
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri validaciji podataka: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def get_rule(
        self,
        name: str
    ) -> Optional[ValidationRuleData]:
        """Dohvaća pravilo validacije."""
        try:
            # Dohvati pravilo
            data = await self._redis.get(f"{self.rule_prefix}{name}")
            if not data:
                return None
                
            # Parsiraj pravilo
            return ValidationRuleData(**json.loads(data))
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu pravila validacije: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    def _validate_data(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> bool:
        """Validira podatke prema shemi."""
        try:
            # Provjeri obavezna polja
            for field, field_schema in schema.items():
                if field_schema.get("required", False):
                    if field not in data:
                        return False
                        
            # Provjeri tipove
            for field, value in data.items():
                if field not in schema:
                    continue
                    
                field_schema = schema[field]
                field_type = field_schema.get("type")
                
                if field_type == "string":
                    if not isinstance(value, str):
                        return False
                elif field_type == "number":
                    if not isinstance(value, (int, float)):
                        return False
                elif field_type == "boolean":
                    if not isinstance(value, bool):
                        return False
                elif field_type == "array":
                    if not isinstance(value, list):
                        return False
                elif field_type == "object":
                    if not isinstance(value, dict):
                        return False
                        
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri validaciji podataka prema shemi: {e}")
            return False
            
    async def _check_rules(self) -> None:
        """Provjerava pravila validacije."""
        while True:
            try:
                # Dohvati sva pravila
                rules = await self._redis.keys(f"{self.rule_prefix}*")
                
                # Provjeri broj pravila
                if len(rules) > self.max_rules:
                    await self._cleanup_rules()
                    
                # Čekaj sljedeći interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri provjeri pravila validacije: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _cleanup_rules(self) -> None:
        """Čisti pravila validacije."""
        try:
            # Dohvati sva pravila
            rules = await self._redis.keys(f"{self.rule_prefix}*")
            
            if not rules:
                return
                
            # Obriši pravila
            await self._redis.delete(*rules)
            
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju pravila validacije: {e}")
            
    def get_stats(self) -> ValidationStats:
        """Dohvaća statistiku validacije."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje validacijom."""
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
            self.logger.error(f"Greška pri zatvaranju validation menadžera: {e}") 