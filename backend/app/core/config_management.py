from typing import Dict, Any, Optional, List, Callable, Union, TypeVar, Generic
import os
import json
import yaml
import toml
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
import consul
import etcd3
import zookeeper
import vault
import boto3
import google.cloud.secretmanager
import azure.keyvault.secrets
from dotenv import load_dotenv
from consul import Consul
from etcd3 import AsyncClient as EtcdClient
from kazoo.client import KazooClient
from hvac import Client as VaultClient
from pydantic import BaseModel, ValidationError
from jsonschema import validate, ValidationError as JSONSchemaError
from marshmallow import Schema, ValidationError as MarshmallowError
from cerberus import Validator as CerberusValidator
from voluptuous import Schema as VoluptuousSchema, Invalid as VoluptuousError
from azure.identity import DefaultAzureCredential
from redis import Redis
from aioredis import Redis as AsyncRedis
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

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class ConfigData:
    id: str
    name: str
    value: Any
    created_at: datetime
    metadata: Dict[str, Any]

@dataclass
class ConfigStats:
    total_reads: int = 0
    total_writes: int = 0
    total_errors: int = 0
    current_keys: int = 0
    peak_keys: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class ConfigManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        config_prefix: str = "config:",
        check_interval: int = 60,  # 1 minuta
        max_keys: int = 1000,
        batch_size: int = 100
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.config_prefix = config_prefix
        self.check_interval = check_interval
        self.max_keys = max_keys
        self.batch_size = batch_size
        
        self.stats = ConfigStats()
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
                self._check_configs()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def get(
        self,
        name: str
    ) -> Optional[Any]:
        """Dohvaća konfiguracijsku vrijednost."""
        try:
            # Dohvati konfiguraciju
            data = await self._redis.get(f"{self.config_prefix}{name}")
            if not data:
                return None
                
            # Parsiraj konfiguraciju
            config = ConfigData(**json.loads(data))
            
            # Ažuriraj statistiku
            self.stats.total_reads += 1
            
            return config.value
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu konfiguracije: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def set(
        self,
        name: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Postavlja konfiguracijsku vrijednost."""
        try:
            # Generiraj ID
            config_id = secrets.token_urlsafe(32)
            
            # Kreiraj konfiguraciju
            config = ConfigData(
                id=config_id,
                name=name,
                value=value,
                created_at=datetime.now(),
                metadata=metadata or {}
            )
            
            # Spremi konfiguraciju
            await self._redis.set(
                f"{self.config_prefix}{name}",
                json.dumps(config.__dict__)
            )
            
            # Ažuriraj statistiku
            self.stats.total_writes += 1
            self.stats.current_keys += 1
            if self.stats.current_keys > self.stats.peak_keys:
                self.stats.peak_keys = self.stats.current_keys
                
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri postavljanju konfiguracije: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def delete(
        self,
        name: str
    ) -> bool:
        """Briše konfiguracijsku vrijednost."""
        try:
            # Obriši konfiguraciju
            await self._redis.delete(f"{self.config_prefix}{name}")
            
            # Ažuriraj statistiku
            self.stats.current_keys -= 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri brisanju konfiguracije: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def load_from_file(
        self,
        file_path: str
    ) -> bool:
        """Učitava konfiguraciju iz datoteke."""
        try:
            # Provjeri datoteku
            if not os.path.exists(file_path):
                return False
                
            # Učitaj datoteku
            with open(file_path, "r") as f:
                configs = json.load(f)
                
            # Spremi konfiguracije
            for name, value in configs.items():
                await self.set(name, value)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri učitavanju konfiguracije iz datoteke: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def save_to_file(
        self,
        file_path: str
    ) -> bool:
        """Sprema konfiguraciju u datoteku."""
        try:
            # Dohvati sve konfiguracije
            configs = await self._redis.keys(f"{self.config_prefix}*")
            
            # Pripremi podatke
            data = {}
            for key in configs:
                config_data = await self._redis.get(key)
                if config_data:
                    config = ConfigData(**json.loads(config_data))
                    data[config.name] = config.value
                    
            # Spremi datoteku
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri spremanju konfiguracije u datoteku: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def _check_configs(self) -> None:
        """Provjerava konfiguracije."""
        while True:
            try:
                # Dohvati sve konfiguracije
                configs = await self._redis.keys(f"{self.config_prefix}*")
                
                # Provjeri broj konfiguracija
                if len(configs) > self.max_keys:
                    await self._cleanup_configs()
                    
                # Čekaj sljedeći interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri provjeri konfiguracija: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _cleanup_configs(self) -> None:
        """Čisti konfiguracije."""
        try:
            # Dohvati sve konfiguracije
            configs = await self._redis.keys(f"{self.config_prefix}*")
            
            if not configs:
                return
                
            # Obriši konfiguracije
            await self._redis.delete(*configs)
            
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju konfiguracija: {e}")
            
    def get_stats(self) -> ConfigStats:
        """Dohvaća statistiku konfiguracije."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje konfiguracijom."""
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
            self.logger.error(f"Greška pri zatvaranju config menadžera: {e}") 