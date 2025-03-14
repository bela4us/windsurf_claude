from typing import Dict, Any, Optional, List, Union, Type, Callable
import traceback
import logging
import json
import threading
from datetime import datetime
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path
import hashlib
import secrets
import time
from redis import Redis
from aioredis import Redis as AsyncRedis

logger = logging.getLogger(__name__)

@dataclass
class ErrorInfo:
    error_id: str
    timestamp: datetime
    error_type: str
    message: str
    stack_trace: str
    context: Dict[str, Any]
    severity: str
    handled: bool
    retry_count: int

@dataclass
class ErrorStats:
    total_errors: int = 0
    total_warnings: int = 0
    total_critical: int = 0
    total_handled: int = 0
    total_unhandled: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class ErrorManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        error_prefix: str = "error:",
        warning_prefix: str = "warning:",
        critical_prefix: str = "critical:",
        max_errors: int = 1000,
        error_ttl: int = 86400,  # 24 sata
        notification_threshold: int = 10,
        notification_window: int = 300  # 5 minuta
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.error_prefix = error_prefix
        self.warning_prefix = warning_prefix
        self.critical_prefix = critical_prefix
        self.max_errors = max_errors
        self.error_ttl = error_ttl
        self.notification_threshold = notification_threshold
        self.notification_window = notification_window
        
        self.stats = ErrorStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        self._error_window: List[float] = []
        
    async def initialize(self) -> None:
        """Inicijalizira Redis konekciju."""
        try:
            self._redis = await AsyncRedis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        level: str = "ERROR"
    ) -> None:
        """Upravlja greškom."""
        try:
            # Kreiraj error entry
            error_entry = {
                "timestamp": time.time(),
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
                "context": context or {},
                "level": level
            }
            
            # Logiraj grešku
            if level == "CRITICAL":
                self.logger.critical(
                    f"{error_entry['message']} - {json.dumps(context)}"
                )
                self.stats.total_critical += 1
            elif level == "WARNING":
                self.logger.warning(
                    f"{error_entry['message']} - {json.dumps(context)}"
                )
                self.stats.total_warnings += 1
            else:
                self.logger.error(
                    f"{error_entry['message']} - {json.dumps(context)}"
                )
                self.stats.total_errors += 1
                
            # Spremi u Redis
            if self._redis:
                error_key = f"{self.error_prefix}{time.time()}"
                await self._redis.set(
                    error_key,
                    json.dumps(error_entry),
                    ex=self.error_ttl
                )
                
                # Dodaj u odgovarajući set
                if level == "CRITICAL":
                    await self._redis.sadd(self.critical_prefix, error_key)
                elif level == "WARNING":
                    await self._redis.sadd(self.warning_prefix, error_key)
                else:
                    await self._redis.sadd(self.error_prefix, error_key)
                    
            # Ažuriraj statistiku
            self.stats.total_handled += 1
            self.stats.last_error = str(error)
            self.stats.last_error_time = datetime.now()
            
            # Provjeri threshold za notifikacije
            await self._check_notification_threshold()
            
        except Exception as e:
            self.logger.error(f"Greška pri upravljanju greškom: {e}")
            self.stats.total_unhandled += 1
            
    async def get_errors(
        self,
        level: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Dohvaća greške."""
        try:
            if not self._redis:
                return []
                
            # Odaberi set za pretragu
            if level == "CRITICAL":
                prefix = self.critical_prefix
            elif level == "WARNING":
                prefix = self.warning_prefix
            else:
                prefix = self.error_prefix
                
            # Dohvati ključeve
            keys = await self._redis.smembers(prefix)
            keys = sorted(keys, reverse=True)[:limit]
            
            # Dohvati greške
            errors = []
            for key in keys:
                error_data = await self._redis.get(key)
                if not error_data:
                    continue
                    
                error_entry = json.loads(error_data)
                
                # Filtriraj po vremenu
                if start_time and error_entry["timestamp"] < start_time:
                    continue
                if end_time and error_entry["timestamp"] > end_time:
                    continue
                    
                errors.append(error_entry)
                
            return errors
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu grešaka: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return []
            
    async def clear_errors(
        self,
        level: Optional[str] = None,
        before_time: Optional[float] = None
    ) -> None:
        """Briše greške."""
        try:
            if not self._redis:
                return
                
            # Odaberi set za brisanje
            if level == "CRITICAL":
                prefix = self.critical_prefix
            elif level == "WARNING":
                prefix = self.warning_prefix
            else:
                prefix = self.error_prefix
                
            # Dohvati ključeve
            keys = await self._redis.smembers(prefix)
            
            # Obriši greške
            for key in keys:
                error_data = await self._redis.get(key)
                if not error_data:
                    continue
                    
                error_entry = json.loads(error_data)
                
                # Filtriraj po vremenu
                if before_time and error_entry["timestamp"] > before_time:
                    continue
                    
                # Obriši iz Redis-a
                await self._redis.delete(key)
                await self._redis.srem(prefix, key)
                
        except Exception as e:
            self.logger.error(f"Greška pri brisanju grešaka: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            
    async def _check_notification_threshold(self) -> None:
        """Provjerava threshold za notifikacije."""
        try:
            # Dodaj trenutno vrijeme u prozor
            self._error_window.append(time.time())
            
            # Ukloni stare greške
            cutoff = time.time() - self.notification_window
            self._error_window = [
                t for t in self._error_window
                if t > cutoff
            ]
            
            # Provjeri threshold
            if len(self._error_window) >= self.notification_threshold:
                # TODO: Implementirati notifikacije
                pass
                
        except Exception as e:
            self.logger.error(f"Greška pri provjeri thresholda: {e}")
            
    def get_stats(self) -> ErrorStats:
        """Dohvaća statistiku grešaka."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje greškama."""
        try:
            if self._redis:
                await self._redis.close()
        except Exception as e:
            self.logger.error(f"Greška pri zatvaranju error menadžera: {e}")

    def _generate_error_id(self) -> str:
        """Generira jedinstveni ID greške"""
        random_bytes = secrets.token_bytes(16)
        return hashlib.sha256(random_bytes).hexdigest()[:12]
    
    def register_handler(self,
                        error_type: str,
                        handler: Callable[[ErrorInfo], None]):
        """Registrira handler za određenu vrstu greške"""
        with self._lock:
            if error_type not in self._error_handlers:
                self._error_handlers[error_type] = []
            self._error_handlers[error_type].append(handler)
    
    def handle_error(self,
                    error: Exception,
                    context: Optional[Dict[str, Any]] = None,
                    severity: str = 'error') -> str:
        """Upravlja greškom"""
        try:
            error_id = self._generate_error_id()
            error_info = ErrorInfo(
                error_id=error_id,
                timestamp=datetime.utcnow(),
                error_type=type(error).__name__,
                message=str(error),
                stack_trace=traceback.format_exc(),
                context=context or {},
                severity=severity,
                handled=False,
                retry_count=0
            )
            
            with self._lock:
                self._errors[error_id] = error_info
                
                # Pozovi odgovarajuće handlere
                if error_info.error_type in self._error_handlers:
                    for handler in self._error_handlers[error_info.error_type]:
                        try:
                            handler(error_info)
                        except Exception as e:
                            logger.error(f"Error in error handler: {str(e)}")
            
            # Logiraj grešku
            log_level = getattr(logging, severity.upper())
            logger.log(log_level, f"Error {error_id}: {error_info.message}")
            
            return error_id
        except Exception as e:
            logger.error(f"Error handling error: {str(e)}")
            return ''
    
    def get_error(self, error_id: str) -> Optional[ErrorInfo]:
        """Dohvaća informacije o grešci"""
        with self._lock:
            return self._errors.get(error_id)
    
    def mark_error_handled(self, error_id: str) -> bool:
        """Označava grešku kao obrađenu"""
        try:
            with self._lock:
                if error_id in self._errors:
                    self._errors[error_id].handled = True
                    return True
                return False
        except Exception as e:
            logger.error(f"Error marking error as handled: {str(e)}")
            return False
    
    def increment_retry_count(self, error_id: str) -> bool:
        """Povećava broj pokušaja za grešku"""
        try:
            with self._lock:
                if error_id in self._errors:
                    self._errors[error_id].retry_count += 1
                    return True
                return False
        except Exception as e:
            logger.error(f"Error incrementing retry count: {str(e)}")
            return False
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Dohvaća statistiku grešaka"""
        try:
            with self._lock:
                stats = {
                    'total_errors': len(self._errors),
                    'handled_errors': sum(1 for e in self._errors.values() if e.handled),
                    'unhandled_errors': sum(1 for e in self._errors.values() if not e.handled),
                    'errors_by_type': {},
                    'errors_by_severity': {},
                    'errors_by_hour': {}
                }
                
                for error in self._errors.values():
                    # Broji po tipu
                    stats['errors_by_type'][error.error_type] = \
                        stats['errors_by_type'].get(error.error_type, 0) + 1
                    
                    # Broji po ozbiljnosti
                    stats['errors_by_severity'][error.severity] = \
                        stats['errors_by_severity'].get(error.severity, 0) + 1
                    
                    # Broji po satu
                    hour = error.timestamp.hour
                    stats['errors_by_hour'][hour] = \
                        stats['errors_by_hour'].get(hour, 0) + 1
                
                return stats
        except Exception as e:
            logger.error(f"Error getting error stats: {str(e)}")
            return {}
    
    def get_recent_errors(self, limit: int = 10) -> List[ErrorInfo]:
        """Dohvaća nedavne greške"""
        try:
            with self._lock:
                sorted_errors = sorted(
                    self._errors.values(),
                    key=lambda x: x.timestamp,
                    reverse=True
                )
                return sorted_errors[:limit]
        except Exception as e:
            logger.error(f"Error getting recent errors: {str(e)}")
            return []
    
    def get_unhandled_errors(self) -> List[ErrorInfo]:
        """Dohvaća neobrađene greške"""
        try:
            with self._lock:
                return [
                    error for error in self._errors.values()
                    if not error.handled
                ]
        except Exception as e:
            logger.error(f"Error getting unhandled errors: {str(e)}")
            return []
    
    def export_errors(self, format: str = 'json') -> str:
        """Izvozi greške u određenom formatu"""
        try:
            with self._lock:
                errors_data = [
                    {
                        'error_id': error.error_id,
                        'timestamp': error.timestamp.isoformat(),
                        'error_type': error.error_type,
                        'message': error.message,
                        'stack_trace': error.stack_trace,
                        'context': error.context,
                        'severity': error.severity,
                        'handled': error.handled,
                        'retry_count': error.retry_count
                    }
                    for error in self._errors.values()
                ]
                
                if format == 'json':
                    return json.dumps(errors_data, indent=2)
                else:
                    raise ValueError(f"Unsupported format: {format}")
        except Exception as e:
            logger.error(f"Error exporting errors: {str(e)}")
            return ''
    
    def clear_errors(self) -> bool:
        """Briše sve greške"""
        try:
            with self._lock:
                self._errors.clear()
                return True
        except Exception as e:
            logger.error(f"Error clearing errors: {str(e)}")
            return False
    
    def shutdown(self):
        """Zatvara error manager"""
        self._executor.shutdown(wait=True) 