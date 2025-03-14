from typing import Dict, Any, Optional, List, Union, Type, Callable
import logging
import asyncio
import time
import json
import secrets
import psutil
from datetime import datetime, timedelta
from dataclasses import dataclass
from redis import Redis
from aioredis import Redis as AsyncRedis

@dataclass
class PerformanceStats:
    total_requests: int = 0
    total_errors: int = 0
    total_time: float = 0.0
    average_time: float = 0.0
    max_time: float = 0.0
    min_time: float = float("inf")
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class PerformanceManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        performance_prefix: str = "performance:",
        check_interval: int = 60,  # 1 minuta
        max_keys: int = 10000,
        batch_size: int = 100
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.performance_prefix = performance_prefix
        self.check_interval = check_interval
        self.max_keys = max_keys
        self.batch_size = batch_size
        
        self.stats = PerformanceStats()
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
                self._check_performance()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def record_request(
        self,
        request_id: str,
        duration: float
    ) -> None:
        """Bilježi zahtjev."""
        try:
            # Generiraj ključ
            request_key = f"{self.performance_prefix}request:{request_id}"
            
            # Kreiraj podatke
            request_data = {
                "request_id": request_id,
                "duration": duration,
                "timestamp": datetime.now().isoformat()
            }
            
            # Spremi podatke
            await self._redis.set(request_key, json.dumps(request_data))
            
            # Ažuriraj statistiku
            self.stats.total_requests += 1
            self.stats.total_time += duration
            self.stats.average_time = self.stats.total_time / self.stats.total_requests
            self.stats.max_time = max(self.stats.max_time, duration)
            self.stats.min_time = min(self.stats.min_time, duration)
            
        except Exception as e:
            self.logger.error(f"Greška pri bilježenju zahtjeva: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            
    async def record_error(
        self,
        request_id: str,
        error: str
    ) -> None:
        """Bilježi grešku."""
        try:
            # Generiraj ključ
            error_key = f"{self.performance_prefix}error:{request_id}"
            
            # Kreiraj podatke
            error_data = {
                "request_id": request_id,
                "error": error,
                "timestamp": datetime.now().isoformat()
            }
            
            # Spremi podatke
            await self._redis.set(error_key, json.dumps(error_data))
            
            # Ažuriraj statistiku
            self.stats.total_errors += 1
            self.stats.last_error = error
            self.stats.last_error_time = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Greška pri bilježenju greške: {e}")
            
    async def get_system_stats(self) -> Dict[str, Any]:
        """Dohvaća statistiku sustava."""
        try:
            # Dohvati CPU
            cpu_percent = psutil.cpu_percent()
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Dohvati memoriju
            memory = psutil.virtual_memory()
            
            # Dohvati disk
            disk = psutil.disk_usage("/")
            
            # Dohvati mrežu
            net_io = psutil.net_io_counters()
            
            # Kreiraj statistiku
            stats = {
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count,
                    "frequency": {
                        "current": cpu_freq.current,
                        "min": cpu_freq.min,
                        "max": cpu_freq.max
                    }
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used,
                    "free": memory.free
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent
                },
                "network": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv
                }
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu statistike sustava: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return {}
            
    async def get_process_stats(self) -> Dict[str, Any]:
        """Dohvaća statistiku procesa."""
        try:
            # Dohvati proces
            process = psutil.Process()
            
            # Dohvati podatke
            with process.oneshot():
                # Kreiraj statistiku
                stats = {
                    "pid": process.pid,
                    "name": process.name(),
                    "status": process.status(),
                    "cpu_percent": process.cpu_percent(),
                    "memory_percent": process.memory_percent(),
                    "memory_info": {
                        "rss": process.memory_info().rss,
                        "vms": process.memory_info().vms
                    },
                    "num_threads": process.num_threads(),
                    "num_fds": process.num_fds(),
                    "create_time": datetime.fromtimestamp(process.create_time()).isoformat()
                }
                
            return stats
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu statistike procesa: {e}")
            self.stats.total_errors += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return {}
            
    async def _check_performance(self) -> None:
        """Provjerava performanse."""
        while True:
            try:
                # Dohvati sve ključeve
                keys = await self._redis.keys(f"{self.performance_prefix}*")
                
                # Provjeri broj ključeva
                if len(keys) > self.max_keys:
                    await self._cleanup_keys()
                    
                # Čekaj sljedeći interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri provjeri performansi: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _cleanup_keys(self) -> None:
        """Čisti ključeve."""
        try:
            # Dohvati sve ključeve
            keys = await self._redis.keys(f"{self.performance_prefix}*")
            
            if not keys:
                return
                
            # Obriši ključeve
            await self._redis.delete(*keys)
            
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju ključeva: {e}")
            
    def get_stats(self) -> PerformanceStats:
        """Dohvaća statistiku performansi."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje performansama."""
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
            self.logger.error(f"Greška pri zatvaranju performance menadžera: {e}") 