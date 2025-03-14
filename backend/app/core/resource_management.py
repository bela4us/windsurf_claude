from typing import Dict, List, Optional, Any, Union, Type, Callable
import psutil
import resource
import logging
from contextlib import contextmanager
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
import os
import asyncio
import json
from redis import Redis
from aioredis import Redis as AsyncRedis
import secrets
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import orjson
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
class ResourceMetrics:
    cpu_percent: float
    memory_percent: float
    disk_usage: Dict[str, float]
    network_io: Dict[str, float]
    timestamp: datetime

@dataclass
class ResourceData:
    id: str
    name: str
    type: str
    status: str
    created_at: datetime
    metadata: Dict[str, Any]

@dataclass
class ResourceStats:
    total_resources: int = 0
    total_allocations: int = 0
    total_frees: int = 0
    total_errors: int = 0
    current_resources: int = 0
    peak_resources: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class ResourceManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        resource_prefix: str = "resource:",
        check_interval: int = 60,  # 1 minuta
        max_resources: int = 1000,
        batch_size: int = 100
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.resource_prefix = resource_prefix
        self.check_interval = check_interval
        self.max_resources = max_resources
        self.batch_size = batch_size
        
        self.stats = ResourceStats()
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
                self._check_resources()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def allocate(
        self,
        name: str,
        type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ResourceData]:
        """Alocira resurs."""
        try:
            # Provjeri postojeći resurs
            if await self._redis.exists(f"{self.resource_prefix}{name}"):
                return None
                
            # Generiraj ID
            resource_id = secrets.token_urlsafe(32)
            
            # Kreiraj resurs
            resource = ResourceData(
                id=resource_id,
                name=name,
                type=type,
                status="allocated",
                created_at=datetime.now(),
                metadata=metadata or {}
            )
            
            # Spremi resurs
            await self._redis.set(
                f"{self.resource_prefix}{name}",
                json.dumps(resource.__dict__)
            )
            
            # Ažuriraj statistiku
            self.stats.total_resources += 1
            self.stats.total_allocations += 1
            self.stats.current_resources += 1
            if self.stats.current_resources > self.stats.peak_resources:
                self.stats.peak_resources = self.stats.current_resources
                
            return resource
            
        except Exception as e:
            self.logger.error(f"Greška pri alokaciji resursa: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def free(
        self,
        name: str
    ) -> bool:
        """Oslobađa resurs."""
        try:
            # Dohvati resurs
            data = await self._redis.get(f"{self.resource_prefix}{name}")
            if not data:
                return False
                
            # Parsiraj resurs
            resource = ResourceData(**json.loads(data))
            
            # Provjeri status
            if resource.status != "allocated":
                return False
                
            # Oslobodi resurs
            resource.status = "freed"
            await self._redis.set(
                f"{self.resource_prefix}{name}",
                json.dumps(resource.__dict__)
            )
            
            # Ažuriraj statistiku
            self.stats.total_frees += 1
            self.stats.current_resources -= 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri oslobađanju resursa: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def get(
        self,
        name: str
    ) -> Optional[ResourceData]:
        """Dohvaća resurs."""
        try:
            # Dohvati resurs
            data = await self._redis.get(f"{self.resource_prefix}{name}")
            if not data:
                return None
                
            # Parsiraj resurs
            return ResourceData(**json.loads(data))
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu resursa: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def update(
        self,
        name: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Ažurira resurs."""
        try:
            # Dohvati resurs
            data = await self._redis.get(f"{self.resource_prefix}{name}")
            if not data:
                return False
                
            # Parsiraj resurs
            resource = ResourceData(**json.loads(data))
            
            # Ažuriraj metapodatke
            resource.metadata.update(metadata)
            
            # Spremi resurs
            await self._redis.set(
                f"{self.resource_prefix}{name}",
                json.dumps(resource.__dict__)
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri ažuriranju resursa: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def _check_resources(self) -> None:
        """Provjerava resurse."""
        while True:
            try:
                # Dohvati sve resurse
                resources = await self._redis.keys(f"{self.resource_prefix}*")
                
                # Provjeri broj resursa
                if len(resources) > self.max_resources:
                    await self._cleanup_resources()
                    
                # Čekaj sljedeći interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri provjeri resursa: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _cleanup_resources(self) -> None:
        """Čisti resurse."""
        try:
            # Dohvati sve resurse
            resources = await self._redis.keys(f"{self.resource_prefix}*")
            
            if not resources:
                return
                
            # Obriši resurse
            await self._redis.delete(*resources)
            
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju resursa: {e}")
            
    def get_stats(self) -> ResourceStats:
        """Dohvaća statistiku resursa."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje resursima."""
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
            self.logger.error(f"Greška pri zatvaranju resource menadžera: {e}")
        
    def start_monitoring(self, interval: float = 1.0) -> None:
        """Pokreće praćenje resursa."""
        if self._monitoring:
            return
            
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_resources,
            args=(interval,),
            daemon=True
        )
        self._monitor_thread.start()
        
    def stop_monitoring(self) -> None:
        """Zaustavlja praćenje resursa."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join()
            
    def _monitor_resources(self, interval: float) -> None:
        """Praći resurse u pozadini."""
        while self._monitoring:
            try:
                metrics = self.get_current_metrics()
                with self._lock:
                    self._metrics.append(metrics)
                    if len(self._metrics) > 1000:  # Zadržavamo zadnjih 1000 mjerenja
                        self._metrics.pop(0)
            except Exception as e:
                self.logger.error(f"Greška pri praćenju resursa: {e}")
            time.sleep(interval)
            
    def get_current_metrics(self) -> ResourceMetrics:
        """Dohvaća trenutne metrike resursa."""
        return ResourceMetrics(
            cpu_percent=self._process.cpu_percent(),
            memory_percent=self._process.memory_percent(),
            disk_usage={
                partition.mountpoint: psutil.disk_usage(partition.mountpoint).percent
                for partition in psutil.disk_partitions()
            },
            network_io={
                interface: psutil.net_io_counters(pernic=True)[interface]._asdict()
                for interface in psutil.net_if_stats().keys()
            },
            timestamp=datetime.now()
        )
        
    def get_metrics_history(self, limit: int = 100) -> List[ResourceMetrics]:
        """Dohvaća povijest metrika."""
        with self._lock:
            return self._metrics[-limit:]
            
    def get_average_metrics(self, window: int = 60) -> ResourceMetrics:
        """Računa prosječne metrike za zadani vremenski prozor."""
        with self._lock:
            recent_metrics = self._metrics[-window:]
            if not recent_metrics:
                return self.get_current_metrics()
                
            return ResourceMetrics(
                cpu_percent=sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics),
                memory_percent=sum(m.memory_percent for m in recent_metrics) / len(recent_metrics),
                disk_usage={
                    mountpoint: sum(m.disk_usage[mountpoint] for m in recent_metrics) / len(recent_metrics)
                    for mountpoint in recent_metrics[0].disk_usage.keys()
                },
                network_io={
                    interface: {
                        key: sum(m.network_io[interface][key] for m in recent_metrics) / len(recent_metrics)
                        for key in recent_metrics[0].network_io[list(recent_metrics[0].network_io.keys())[0]].keys()
                    }
                    for interface in recent_metrics[0].network_io.keys()
                },
                timestamp=datetime.now()
            )
            
    def get_resource_usage(self) -> Dict[str, Any]:
        """Dohvaća trenutno korištenje resursa."""
        metrics = self.get_current_metrics()
        return {
            "cpu": {
                "percent": metrics.cpu_percent,
                "count": psutil.cpu_count(),
                "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
            },
            "memory": {
                "percent": metrics.memory_percent,
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "used": psutil.virtual_memory().used
            },
            "disk": {
                mountpoint: {
                    "percent": usage,
                    "total": psutil.disk_usage(mountpoint).total,
                    "used": psutil.disk_usage(mountpoint).used,
                    "free": psutil.disk_usage(mountpoint).free
                }
                for mountpoint, usage in metrics.disk_usage.items()
            },
            "network": {
                interface: {
                    "bytes_sent": stats["bytes_sent"],
                    "bytes_recv": stats["bytes_recv"],
                    "packets_sent": stats["packets_sent"],
                    "packets_recv": stats["packets_recv"]
                }
                for interface, stats in metrics.network_io.items()
            }
        }
        
    def get_process_info(self) -> Dict[str, Any]:
        """Dohvaća informacije o trenutnom procesu."""
        return {
            "pid": self._process.pid,
            "name": self._process.name(),
            "status": self._process.status(),
            "create_time": datetime.fromtimestamp(self._process.create_time()),
            "cpu_percent": self._process.cpu_percent(),
            "memory_percent": self._process.memory_percent(),
            "num_threads": self._process.num_threads(),
            "num_fds": self._process.num_fds(),
            "username": self._process.username(),
            "cmdline": self._process.cmdline()
        }
        
    def get_system_info(self) -> Dict[str, Any]:
        """Dohvaća informacije o sustavu."""
        return {
            "platform": {
                "system": psutil.sys.platform,
                "release": psutil.sys.release(),
                "version": psutil.sys.version,
                "machine": psutil.sys.machine
            },
            "cpu": {
                "count": psutil.cpu_count(),
                "count_logical": psutil.cpu_count(logical=True),
                "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                "stats": psutil.cpu_stats()._asdict(),
                "percent": psutil.cpu_percent(interval=1)
            },
            "memory": psutil.virtual_memory()._asdict(),
            "swap": psutil.swap_memory()._asdict(),
            "disk": {
                partition.mountpoint: psutil.disk_usage(partition.mountpoint)._asdict()
                for partition in psutil.disk_partitions()
            },
            "network": {
                interface: psutil.net_if_stats()[interface]._asdict()
                for interface in psutil.net_if_stats().keys()
            }
        }
        
    def optimize_memory(self) -> None:
        """Optimizira korištenje memorije."""
        import gc
        gc.collect()
        
    def cleanup_resources(self) -> None:
        """Čisti resurse."""
        self.stop_monitoring()
        self.optimize_memory()
        
    def shutdown(self) -> None:
        """Zaustavlja upravljanje resursima."""
        self.cleanup_resources()
    
    def monitor_process(self, pid: Optional[int] = None) -> Dict[str, Any]:
        """Praći specifični proces"""
        target_process = psutil.Process(pid) if pid else self._process
        return {
            'pid': target_process.pid,
            'name': target_process.name(),
            'status': target_process.status(),
            'cpu_percent': target_process.cpu_percent(),
            'memory_percent': target_process.memory_percent(),
            'num_threads': target_process.num_threads(),
            'num_fds': target_process.num_fds(),
            'create_time': datetime.fromtimestamp(target_process.create_time())
        }
    
    @contextmanager
    def resource_limit(self, 
                     memory_limit_mb: Optional[int] = None,
                     cpu_percent: Optional[float] = None):
        """Kontekstni menadžer za ograničavanje resursa"""
        original_memory_limit = resource.getrlimit(resource.RLIMIT_AS)
        original_cpu_time = resource.getrlimit(resource.RLIMIT_CPU)
        
        try:
            if memory_limit_mb:
                memory_bytes = memory_limit_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            
            if cpu_percent:
                cpu_seconds = int(cpu_percent * 60)
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            
            yield
            
        finally:
            resource.setrlimit(resource.RLIMIT_AS, original_memory_limit)
            resource.setrlimit(resource.RLIMIT_CPU, original_cpu_time)
    
    def get_system_info(self) -> Dict[str, Any]:
        """Dohvaća informacije o sustavu"""
        return {
            'cpu_count': psutil.cpu_count(),
            'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            'memory_total': psutil.virtual_memory().total,
            'memory_available': psutil.virtual_memory().available,
            'disk_total': psutil.disk_usage('/').total,
            'disk_free': psutil.disk_usage('/').free,
            'network_interfaces': psutil.net_if_stats()
        }
    
    def cleanup_resources(self):
        """Čisti resurse"""
        self.stop_monitoring()
        self.optimize_memory()
        
        # Zatvara file handle-ove
        for fd in range(3, resource.getrlimit(resource.RLIMIT_NOFILE)[0]):
            try:
                os.close(fd)
            except OSError:
                pass 