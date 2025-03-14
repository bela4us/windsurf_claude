from typing import Dict, Any, Optional, List, Callable, Union, Type
import asyncio
import json
import threading
from datetime import datetime
from dataclasses import dataclass
import logging
from pathlib import Path
import orjson
import time
from functools import wraps
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
import queue
import gzip
import shutil
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import structlog
import elasticsearch
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
import os
from redis import Redis
from aioredis import Redis as AsyncRedis

logger = logging.getLogger(__name__)

@dataclass
class LogStats:
    total_logs: int = 0
    total_bytes: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    total_info: int = 0
    total_debug: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class LogManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        log_dir: str = "logs",
        log_prefix: str = "log:",
        max_file_size: int = 10 * 1024 * 1024,  # 10 MB
        max_files: int = 10,
        compression_threshold: int = 1024 * 1024,  # 1 MB
        batch_size: int = 100,
        processing_interval: int = 60,  # 1 minuta
        retention_days: int = 30
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.log_dir = log_dir
        self.log_prefix = log_prefix
        self.max_file_size = max_file_size
        self.max_files = max_files
        self.compression_threshold = compression_threshold
        self.batch_size = batch_size
        self.processing_interval = processing_interval
        self.retention_days = retention_days
        
        self.stats = LogStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        self._processing_task: Optional[asyncio.Task] = None
        
        # Kreiraj direktorij za logove
        os.makedirs(log_dir, exist_ok=True)
        
    async def initialize(self) -> None:
        """Inicijalizira Redis konekciju i pokreće procesiranje."""
        try:
            self._redis = await AsyncRedis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Pokreni procesiranje
            self._processing_task = asyncio.create_task(
                self._process_logs()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def log(
        self,
        level: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Bilježi log."""
        try:
            # Kreiraj log entry
            log_entry = {
                "timestamp": time.time(),
                "level": level,
                "message": message,
                "context": context or {}
            }
            
            # Generiraj ključ
            log_key = f"{self.log_prefix}{level}"
            
            # Spremi log
            await self._redis.lpush(
                log_key,
                json.dumps(log_entry)
            )
            
            # Ažuriraj statistiku
            self.stats.total_logs += 1
            self.stats.total_bytes += len(json.dumps(log_entry))
            
            if level == "ERROR":
                self.stats.total_errors += 1
            elif level == "WARNING":
                self.stats.total_warnings += 1
            elif level == "INFO":
                self.stats.total_info += 1
            elif level == "DEBUG":
                self.stats.total_debug += 1
                
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri bilježenju loga: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def _process_logs(self) -> None:
        """Procesira logove iz Redis-a."""
        while True:
            try:
                # Dohvati sve razine
                levels = await self._redis.keys(f"{self.log_prefix}*")
                
                for level_key in levels:
                    # Dohvati batch logova
                    logs = await self._redis.lrange(
                        level_key,
                        0,
                        self.batch_size - 1
                    )
                    
                    if not logs:
                        continue
                        
                    # Procesiraj logove
                    for log in logs:
                        try:
                            # Parsiraj log
                            log_data = json.loads(log)
                            
                            # Spremi u datoteku
                            await self._save_to_file(log_data)
                            
                            # Ukloni iz Redis-a
                            await self._redis.lrem(level_key, 1, log)
                            
                        except Exception as e:
                            self.logger.error(
                                f"Greška pri procesiranju loga: {e}"
                            )
                            
                # Očisti stare datoteke
                await self._cleanup_old_files()
                
                # Kompresiraj velike datoteke
                await self._compress_large_files()
                
                # Čekaj sljedeći interval
                await asyncio.sleep(self.processing_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri procesiranju logova: {e}")
                await asyncio.sleep(self.processing_interval)
                
    async def _save_to_file(
        self,
        log_data: Dict[str, Any]
    ) -> None:
        """Sprema log u datoteku."""
        try:
            # Generiraj ime datoteke
            date = datetime.fromtimestamp(log_data["timestamp"])
            filename = f"{date.strftime('%Y-%m-%d')}.log"
            filepath = os.path.join(self.log_dir, filename)
            
            # Kreiraj log liniju
            log_line = (
                f"{date.isoformat()} "
                f"[{log_data['level']}] "
                f"{log_data['message']}"
            )
            
            if log_data["context"]:
                log_line += f" {json.dumps(log_data['context'])}"
                
            log_line += "\n"
            
            # Spremi u datoteku
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(log_line)
                
        except Exception as e:
            self.logger.error(f"Greška pri spremanju u datoteku: {e}")
            
    async def _cleanup_old_files(self) -> None:
        """Briše stare datoteke."""
        try:
            # Dohvati sve datoteke
            files = os.listdir(self.log_dir)
            
            # Provjeri svaku datoteku
            for filename in files:
                filepath = os.path.join(self.log_dir, filename)
                
                # Provjeri starost
                mtime = os.path.getmtime(filepath)
                age = time.time() - mtime
                
                if age > self.retention_days * 24 * 60 * 60:
                    # Obriši datoteku
                    os.remove(filepath)
                    
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju starih datoteka: {e}")
            
    async def _compress_large_files(self) -> None:
        """Kompresira velike datoteke."""
        try:
            # Dohvati sve datoteke
            files = os.listdir(self.log_dir)
            
            # Provjeri svaku datoteku
            for filename in files:
                if filename.endswith(".gz"):
                    continue
                    
                filepath = os.path.join(self.log_dir, filename)
                
                # Provjeri veličinu
                size = os.path.getsize(filepath)
                if size < self.compression_threshold:
                    continue
                    
                # Kompresiraj datoteku
                gz_filepath = f"{filepath}.gz"
                with open(filepath, "rb") as f_in:
                    with gzip.open(gz_filepath, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                        
                # Obriši original
                os.remove(filepath)
                
        except Exception as e:
            self.logger.error(f"Greška pri kompresiranju datoteka: {e}")
            
    def get_stats(self) -> LogStats:
        """Dohvaća statistiku logova."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje logovima."""
        try:
            # Zaustavi procesiranje
            if self._processing_task:
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass
                    
            # Zatvori Redis
            if self._redis:
                await self._redis.close()
                
        except Exception as e:
            self.logger.error(f"Greška pri zatvaranju log menadžera: {e}") 