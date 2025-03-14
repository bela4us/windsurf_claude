<<<<<<< HEAD
from typing import Dict, Optional, Any, List, Union, Type, Callable
import logging
import logging.handlers
import os
from datetime import datetime
import json
import threading
from dataclasses import dataclass
import queue
import asyncio
from concurrent.futures import ThreadPoolExecutor
import gzip
import shutil
from pathlib import Path
from redis import Redis
from aioredis import Redis as AsyncRedis
import time

logger = logging.getLogger(__name__)

@dataclass
class LogEntry:
    timestamp: datetime
    level: str
    message: str
    extra: Dict[str, Any]
    thread_id: int
    process_id: int

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
        log_dir: str = "logs",
        redis_url: Optional[str] = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 5,
        when: str = "midnight",
        interval: int = 1,
        compression: bool = True,
        compression_threshold: int = 1024 * 1024,  # 1 MB
        log_prefix: str = "log:",
        error_prefix: str = "error:",
        warning_prefix: str = "warning:",
        info_prefix: str = "info:",
        debug_prefix: str = "debug:"
    ):
        self.logger = logging.getLogger(__name__)
        self.log_dir = log_dir
        self.redis_url = redis_url
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.when = when
        self.interval = interval
        self.compression = compression
        self.compression_threshold = compression_threshold
        self.log_prefix = log_prefix
        self.error_prefix = error_prefix
        self.warning_prefix = warning_prefix
        self.info_prefix = info_prefix
        self.debug_prefix = debug_prefix
        
        self.stats = LogStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        self._handlers: Dict[str, logging.Handler] = {}
        
    async def initialize(self) -> None:
        """Inicijalizira logiranje."""
        try:
            # Kreiraj direktorij za logove
            os.makedirs(self.log_dir, exist_ok=True)
            
            # Inicijaliziraj Redis ako je konfiguriran
            if self.redis_url:
                self._redis = await AsyncRedis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                
            # Postavi handlere
            self._setup_handlers()
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji logiranja: {e}")
            raise
            
    def _setup_handlers(self) -> None:
        """Postavlja handlere za logiranje."""
        try:
            # Handler za rotaciju po veličini
            size_handler = logging.handlers.RotatingFileHandler(
                os.path.join(self.log_dir, "app.log"),
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding="utf-8"
            )
            size_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            self._handlers["size"] = size_handler
            
            # Handler za rotaciju po vremenu
            time_handler = logging.handlers.TimedRotatingFileHandler(
                os.path.join(self.log_dir, "app.log"),
                when=self.when,
                interval=self.interval,
                backupCount=self.backup_count,
                encoding="utf-8"
            )
            time_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            self._handlers["time"] = time_handler
            
            # Dodaj handlere u logger
            for handler in self._handlers.values():
                self.logger.addHandler(handler)
                
        except Exception as e:
            self.logger.error(f"Greška pri postavljanju handlera: {e}")
            raise
            
    async def log(
        self,
        level: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Logira poruku."""
        try:
            # Kreiraj log entry
            log_entry = {
                "timestamp": time.time(),
                "level": level,
                "message": message,
                "data": data or {}
            }
            
            # Logiraj u datoteku
            log_message = f"{message} - {json.dumps(data)}" if data else message
            if level == "ERROR":
                self.logger.error(log_message)
                self.stats.total_errors += 1
            elif level == "WARNING":
                self.logger.warning(log_message)
                self.stats.total_warnings += 1
            elif level == "INFO":
                self.logger.info(log_message)
                self.stats.total_info += 1
            else:
                self.logger.debug(log_message)
                self.stats.total_debug += 1
                
            # Spremi u Redis ako je konfiguriran
            if self._redis:
                log_key = f"{self.log_prefix}{time.time()}"
                await self._redis.set(
                    log_key,
                    json.dumps(log_entry)
                )
                
                # Dodaj u odgovarajući set
                if level == "ERROR":
                    await self._redis.sadd(self.error_prefix, log_key)
                elif level == "WARNING":
                    await self._redis.sadd(self.warning_prefix, log_key)
                elif level == "INFO":
                    await self._redis.sadd(self.info_prefix, log_key)
                else:
                    await self._redis.sadd(self.debug_prefix, log_key)
                    
            self.stats.total_logs += 1
            self.stats.total_bytes += len(str(log_entry).encode())
            
        except Exception as e:
            self.logger.error(f"Greška pri logiranju: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            
    async def compress_logs(self) -> None:
        """Kompresira log datoteke."""
        try:
            if not self.compression:
                return
                
            # Pronađi sve log datoteke
            for filename in os.listdir(self.log_dir):
                if not filename.endswith(".log"):
                    continue
                    
                filepath = os.path.join(self.log_dir, filename)
                filesize = os.path.getsize(filepath)
                
                # Kompresiraj ako je veća od praga
                if filesize > self.compression_threshold:
                    gz_filepath = f"{filepath}.gz"
                    
                    # Kompresiraj datoteku
                    with open(filepath, "rb") as f_in:
                        with gzip.open(gz_filepath, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                            
                    # Obriši originalnu datoteku
                    os.remove(filepath)
                    
        except Exception as e:
            self.logger.error(f"Greška pri kompresiranju logova: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            
    async def get_logs(
        self,
        level: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Dohvaća logove."""
        try:
            if not self._redis:
                return []
                
            # Odaberi set za pretragu
            if level == "ERROR":
                prefix = self.error_prefix
            elif level == "WARNING":
                prefix = self.warning_prefix
            elif level == "INFO":
                prefix = self.info_prefix
            elif level == "DEBUG":
                prefix = self.debug_prefix
            else:
                prefix = self.log_prefix
                
            # Dohvati ključeve
            keys = await self._redis.smembers(prefix)
            keys = sorted(keys, reverse=True)[:limit]
            
            # Dohvati logove
            logs = []
            for key in keys:
                log_data = await self._redis.get(key)
                if not log_data:
                    continue
                    
                log_entry = json.loads(log_data)
                
                # Filtriraj po vremenu
                if start_time and log_entry["timestamp"] < start_time:
                    continue
                if end_time and log_entry["timestamp"] > end_time:
                    continue
                    
                logs.append(log_entry)
                
            return logs
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu logova: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return []
            
    async def clear_logs(
        self,
        level: Optional[str] = None,
        before_time: Optional[float] = None
    ) -> None:
        """Briše logove."""
        try:
            if not self._redis:
                return
                
            # Odaberi set za brisanje
            if level == "ERROR":
                prefix = self.error_prefix
            elif level == "WARNING":
                prefix = self.warning_prefix
            elif level == "INFO":
                prefix = self.info_prefix
            elif level == "DEBUG":
                prefix = self.debug_prefix
            else:
                prefix = self.log_prefix
                
            # Dohvati ključeve
            keys = await self._redis.smembers(prefix)
            
            # Obriši logove
            for key in keys:
                log_data = await self._redis.get(key)
                if not log_data:
                    continue
                    
                log_entry = json.loads(log_data)
                
                # Filtriraj po vremenu
                if before_time and log_entry["timestamp"] > before_time:
                    continue
                    
                # Obriši iz Redis-a
                await self._redis.delete(key)
                await self._redis.srem(prefix, key)
                
        except Exception as e:
            self.logger.error(f"Greška pri brisanju logova: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            
    def get_stats(self) -> LogStats:
        """Dohvaća statistiku logiranja."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja logiranje."""
        try:
            # Kompresiraj logove
            await self.compress_logs()
            
            # Zatvori handlere
            for handler in self._handlers.values():
                handler.close()
                
            # Zatvori Redis konekciju
            if self._redis:
                await self._redis.close()
                
        except Exception as e:
            self.logger.error(f"Greška pri zatvaranju log menadžera: {e}")
    
    def compress_logs(self):
        """Kompresira stare log datoteke"""
        try:
            log_files = sorted(
                self.log_dir.glob('app.log.*'),
                key=lambda x: x.stat().st_mtime
            )
            
            for log_file in log_files:
                if not log_file.suffix == '.gz':
                    gz_file = log_file.with_suffix('.log.gz')
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(gz_file, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    log_file.unlink()
        except Exception as e:
            logger.error(f"Error compressing logs: {str(e)}")
    
    def cleanup_old_logs(self, days: int = 30):
        """Briše stare log datoteke"""
        try:
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
            
            for log_file in self.log_dir.glob('app.log.*'):
                if log_file.stat().st_mtime < cutoff_date:
                    log_file.unlink()
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {str(e)}")
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Dohvaća statistiku logova"""
        try:
            stats = {
                'total_size': 0,
                'file_count': 0,
                'oldest_log': None,
                'newest_log': None,
                'compressed_count': 0
            }
            
            for log_file in self.log_dir.glob('app.log.*'):
                stats['total_size'] += log_file.stat().st_size
                stats['file_count'] += 1
                
                if log_file.suffix == '.gz':
                    stats['compressed_count'] += 1
                
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if not stats['oldest_log'] or mtime < stats['oldest_log']:
                    stats['oldest_log'] = mtime
                if not stats['newest_log'] or mtime > stats['newest_log']:
                    stats['newest_log'] = mtime
            
            return stats
        except Exception as e:
            logger.error(f"Error getting log stats: {str(e)}")
            return {}
    
    def search_logs(self,
                   query: str,
                   level: Optional[str] = None,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Pretražuje logove"""
        try:
            results = []
            
            for log_file in self.log_dir.glob('app.log*'):
                if log_file.suffix == '.gz':
                    opener = gzip.open
                else:
                    opener = open
                
                with opener(log_file, 'rt', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            
                            if level and entry['level'] != level:
                                continue
                            
                            entry_time = datetime.fromisoformat(entry['timestamp'])
                            if start_date and entry_time < start_date:
                                continue
                            if end_date and entry_time > end_date:
                                continue
                            
                            if query.lower() in entry['message'].lower():
                                results.append(entry)
                        except json.JSONDecodeError:
                            continue
            
            return results
        except Exception as e:
            logger.error(f"Error searching logs: {str(e)}")
            return []
    
    def shutdown(self):
        """Zatvara log manager"""
        self._queue.put(None)
=======
from typing import Dict, Optional, Any, List, Union, Type, Callable
import logging
import logging.handlers
import os
from datetime import datetime
import json
import threading
from dataclasses import dataclass
import queue
import asyncio
from concurrent.futures import ThreadPoolExecutor
import gzip
import shutil
from pathlib import Path
from redis import Redis
from aioredis import Redis as AsyncRedis
import time

logger = logging.getLogger(__name__)

@dataclass
class LogEntry:
    timestamp: datetime
    level: str
    message: str
    extra: Dict[str, Any]
    thread_id: int
    process_id: int

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
        log_dir: str = "logs",
        redis_url: Optional[str] = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 5,
        when: str = "midnight",
        interval: int = 1,
        compression: bool = True,
        compression_threshold: int = 1024 * 1024,  # 1 MB
        log_prefix: str = "log:",
        error_prefix: str = "error:",
        warning_prefix: str = "warning:",
        info_prefix: str = "info:",
        debug_prefix: str = "debug:"
    ):
        self.logger = logging.getLogger(__name__)
        self.log_dir = log_dir
        self.redis_url = redis_url
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.when = when
        self.interval = interval
        self.compression = compression
        self.compression_threshold = compression_threshold
        self.log_prefix = log_prefix
        self.error_prefix = error_prefix
        self.warning_prefix = warning_prefix
        self.info_prefix = info_prefix
        self.debug_prefix = debug_prefix
        
        self.stats = LogStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        self._handlers: Dict[str, logging.Handler] = {}
        
    async def initialize(self) -> None:
        """Inicijalizira logiranje."""
        try:
            # Kreiraj direktorij za logove
            os.makedirs(self.log_dir, exist_ok=True)
            
            # Inicijaliziraj Redis ako je konfiguriran
            if self.redis_url:
                self._redis = await AsyncRedis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                
            # Postavi handlere
            self._setup_handlers()
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji logiranja: {e}")
            raise
            
    def _setup_handlers(self) -> None:
        """Postavlja handlere za logiranje."""
        try:
            # Handler za rotaciju po veličini
            size_handler = logging.handlers.RotatingFileHandler(
                os.path.join(self.log_dir, "app.log"),
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding="utf-8"
            )
            size_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            self._handlers["size"] = size_handler
            
            # Handler za rotaciju po vremenu
            time_handler = logging.handlers.TimedRotatingFileHandler(
                os.path.join(self.log_dir, "app.log"),
                when=self.when,
                interval=self.interval,
                backupCount=self.backup_count,
                encoding="utf-8"
            )
            time_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            self._handlers["time"] = time_handler
            
            # Dodaj handlere u logger
            for handler in self._handlers.values():
                self.logger.addHandler(handler)
                
        except Exception as e:
            self.logger.error(f"Greška pri postavljanju handlera: {e}")
            raise
            
    async def log(
        self,
        level: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Logira poruku."""
        try:
            # Kreiraj log entry
            log_entry = {
                "timestamp": time.time(),
                "level": level,
                "message": message,
                "data": data or {}
            }
            
            # Logiraj u datoteku
            log_message = f"{message} - {json.dumps(data)}" if data else message
            if level == "ERROR":
                self.logger.error(log_message)
                self.stats.total_errors += 1
            elif level == "WARNING":
                self.logger.warning(log_message)
                self.stats.total_warnings += 1
            elif level == "INFO":
                self.logger.info(log_message)
                self.stats.total_info += 1
            else:
                self.logger.debug(log_message)
                self.stats.total_debug += 1
                
            # Spremi u Redis ako je konfiguriran
            if self._redis:
                log_key = f"{self.log_prefix}{time.time()}"
                await self._redis.set(
                    log_key,
                    json.dumps(log_entry)
                )
                
                # Dodaj u odgovarajući set
                if level == "ERROR":
                    await self._redis.sadd(self.error_prefix, log_key)
                elif level == "WARNING":
                    await self._redis.sadd(self.warning_prefix, log_key)
                elif level == "INFO":
                    await self._redis.sadd(self.info_prefix, log_key)
                else:
                    await self._redis.sadd(self.debug_prefix, log_key)
                    
            self.stats.total_logs += 1
            self.stats.total_bytes += len(str(log_entry).encode())
            
        except Exception as e:
            self.logger.error(f"Greška pri logiranju: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            
    async def compress_logs(self) -> None:
        """Kompresira log datoteke."""
        try:
            if not self.compression:
                return
                
            # Pronađi sve log datoteke
            for filename in os.listdir(self.log_dir):
                if not filename.endswith(".log"):
                    continue
                    
                filepath = os.path.join(self.log_dir, filename)
                filesize = os.path.getsize(filepath)
                
                # Kompresiraj ako je veća od praga
                if filesize > self.compression_threshold:
                    gz_filepath = f"{filepath}.gz"
                    
                    # Kompresiraj datoteku
                    with open(filepath, "rb") as f_in:
                        with gzip.open(gz_filepath, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                            
                    # Obriši originalnu datoteku
                    os.remove(filepath)
                    
        except Exception as e:
            self.logger.error(f"Greška pri kompresiranju logova: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            
    async def get_logs(
        self,
        level: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Dohvaća logove."""
        try:
            if not self._redis:
                return []
                
            # Odaberi set za pretragu
            if level == "ERROR":
                prefix = self.error_prefix
            elif level == "WARNING":
                prefix = self.warning_prefix
            elif level == "INFO":
                prefix = self.info_prefix
            elif level == "DEBUG":
                prefix = self.debug_prefix
            else:
                prefix = self.log_prefix
                
            # Dohvati ključeve
            keys = await self._redis.smembers(prefix)
            keys = sorted(keys, reverse=True)[:limit]
            
            # Dohvati logove
            logs = []
            for key in keys:
                log_data = await self._redis.get(key)
                if not log_data:
                    continue
                    
                log_entry = json.loads(log_data)
                
                # Filtriraj po vremenu
                if start_time and log_entry["timestamp"] < start_time:
                    continue
                if end_time and log_entry["timestamp"] > end_time:
                    continue
                    
                logs.append(log_entry)
                
            return logs
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu logova: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return []
            
    async def clear_logs(
        self,
        level: Optional[str] = None,
        before_time: Optional[float] = None
    ) -> None:
        """Briše logove."""
        try:
            if not self._redis:
                return
                
            # Odaberi set za brisanje
            if level == "ERROR":
                prefix = self.error_prefix
            elif level == "WARNING":
                prefix = self.warning_prefix
            elif level == "INFO":
                prefix = self.info_prefix
            elif level == "DEBUG":
                prefix = self.debug_prefix
            else:
                prefix = self.log_prefix
                
            # Dohvati ključeve
            keys = await self._redis.smembers(prefix)
            
            # Obriši logove
            for key in keys:
                log_data = await self._redis.get(key)
                if not log_data:
                    continue
                    
                log_entry = json.loads(log_data)
                
                # Filtriraj po vremenu
                if before_time and log_entry["timestamp"] > before_time:
                    continue
                    
                # Obriši iz Redis-a
                await self._redis.delete(key)
                await self._redis.srem(prefix, key)
                
        except Exception as e:
            self.logger.error(f"Greška pri brisanju logova: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            
    def get_stats(self) -> LogStats:
        """Dohvaća statistiku logiranja."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja logiranje."""
        try:
            # Kompresiraj logove
            await self.compress_logs()
            
            # Zatvori handlere
            for handler in self._handlers.values():
                handler.close()
                
            # Zatvori Redis konekciju
            if self._redis:
                await self._redis.close()
                
        except Exception as e:
            self.logger.error(f"Greška pri zatvaranju log menadžera: {e}")
    
    def compress_logs(self):
        """Kompresira stare log datoteke"""
        try:
            log_files = sorted(
                self.log_dir.glob('app.log.*'),
                key=lambda x: x.stat().st_mtime
            )
            
            for log_file in log_files:
                if not log_file.suffix == '.gz':
                    gz_file = log_file.with_suffix('.log.gz')
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(gz_file, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    log_file.unlink()
        except Exception as e:
            logger.error(f"Error compressing logs: {str(e)}")
    
    def cleanup_old_logs(self, days: int = 30):
        """Briše stare log datoteke"""
        try:
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
            
            for log_file in self.log_dir.glob('app.log.*'):
                if log_file.stat().st_mtime < cutoff_date:
                    log_file.unlink()
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {str(e)}")
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Dohvaća statistiku logova"""
        try:
            stats = {
                'total_size': 0,
                'file_count': 0,
                'oldest_log': None,
                'newest_log': None,
                'compressed_count': 0
            }
            
            for log_file in self.log_dir.glob('app.log.*'):
                stats['total_size'] += log_file.stat().st_size
                stats['file_count'] += 1
                
                if log_file.suffix == '.gz':
                    stats['compressed_count'] += 1
                
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if not stats['oldest_log'] or mtime < stats['oldest_log']:
                    stats['oldest_log'] = mtime
                if not stats['newest_log'] or mtime > stats['newest_log']:
                    stats['newest_log'] = mtime
            
            return stats
        except Exception as e:
            logger.error(f"Error getting log stats: {str(e)}")
            return {}
    
    def search_logs(self,
                   query: str,
                   level: Optional[str] = None,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Pretražuje logove"""
        try:
            results = []
            
            for log_file in self.log_dir.glob('app.log*'):
                if log_file.suffix == '.gz':
                    opener = gzip.open
                else:
                    opener = open
                
                with opener(log_file, 'rt', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            
                            if level and entry['level'] != level:
                                continue
                            
                            entry_time = datetime.fromisoformat(entry['timestamp'])
                            if start_date and entry_time < start_date:
                                continue
                            if end_date and entry_time > end_date:
                                continue
                            
                            if query.lower() in entry['message'].lower():
                                results.append(entry)
                        except json.JSONDecodeError:
                            continue
            
            return results
        except Exception as e:
            logger.error(f"Error searching logs: {str(e)}")
            return []
    
    def shutdown(self):
        """Zatvara log manager"""
        self._queue.put(None)
>>>>>>> c45eb88e3e23e6f6a3bf252c5a572f1c5cdb8266
        self._executor.shutdown(wait=True) 