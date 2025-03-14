from typing import Any, Callable, Dict, List, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
import asyncio
from celery import Celery
from celery.result import AsyncResult
import logging
from datetime import datetime, timedelta
import threading
from pathlib import Path
import json
import pickle
import hashlib
import secrets
import aioredis
import statistics
import redis
import time
from dataclasses import dataclass
from functools import wraps
import uuid

logger = logging.getLogger(__name__)

@dataclass
class TaskInfo:
    task_id: str
    name: str
    args: List[Any]
    kwargs: Dict[str, Any]
    status: str
    result: Optional[Any]
    error: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    retry_count: int

@dataclass
class TaskStats:
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    pending_tasks: int = 0
    avg_processing_time: float = 0.0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class AsyncProcessor:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        celery_broker: str = "redis://localhost:6379/1",
        celery_backend: str = "redis://localhost:6379/2",
        max_retries: int = 3,
        retry_delay: int = 60,
        task_timeout: int = 3600,
        cleanup_days: int = 7
    ):
        self.logger = logging.getLogger(__name__)
        self.redis = redis.from_url(redis_url)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.task_timeout = task_timeout
        self.cleanup_days = cleanup_days
        
        self.celery = Celery(
            "async_processor",
            broker=celery_broker,
            backend=celery_backend
        )
        self.celery.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="UTC",
            enable_utc=True,
            task_track_started=True,
            task_time_limit=task_timeout,
            task_soft_time_limit=task_timeout - 300,
            worker_max_tasks_per_child=1000,
            worker_prefetch_multiplier=1
        )
        
        self.stats = TaskStats()
        self._start_cleanup_task()
        
    def _start_cleanup_task(self) -> None:
        """Započinje periodično čišćenje starih zadataka."""
        asyncio.create_task(self._cleanup_old_tasks())
        
    async def _cleanup_old_tasks(self) -> None:
        """Čisti zadatke starije od zadano dana."""
        while True:
            try:
                await asyncio.sleep(86400)  # Jednom dnevno
                cutoff_date = datetime.now() - timedelta(days=self.cleanup_days)
                
                # Očisti Redis
                pattern = "task:*"
                keys = self.redis.keys(pattern)
                
                for key in keys:
                    task_data = self.redis.get(key)
                    if task_data:
                        task = json.loads(task_data)
                        if datetime.fromisoformat(task["created_at"]) < cutoff_date:
                            self.redis.delete(key)
                            
                # Očisti Celery rezultate
                self.celery.control.purge()
                
            except Exception as e:
                self.logger.error(f"Greška pri čišćenju starih zadataka: {e}")
                
    async def process_batch(
        self,
        items: List[Any],
        process_func: callable,
        batch_size: int = 100
    ) -> List[Any]:
        """Procesira batch stavki asinkrono."""
        try:
            tasks = []
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                task = self.schedule_task(process_func, batch)
                tasks.append(task)
                
            results = await asyncio.gather(*tasks)
            return [item for sublist in results for item in sublist]
            
        except Exception as e:
            self.logger.error(f"Greška pri batch procesiranju: {e}")
            return []
            
    def schedule_task(
        self,
        func: callable,
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
        priority: int = 0
    ) -> str:
        """Zakazuje zadatak za izvršavanje."""
        try:
            task_id = str(uuid.uuid4())
            task_data = {
                "id": task_id,
                "func": func.__name__,
                "args": args or (),
                "kwargs": kwargs or {},
                "priority": priority,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "retries": 0
            }
            
            # Spremi u Redis
            self.redis.set(
                f"task:{task_id}",
                json.dumps(task_data),
                ex=self.task_timeout
            )
            
            # Pošalji u Celery
            task = self.celery.send_task(
                func.__name__,
                args=args,
                kwargs=kwargs,
                task_id=task_id,
                priority=priority
            )
            
            self.stats.total_tasks += 1
            self.stats.pending_tasks += 1
            
            return task_id
            
        except Exception as e:
            self.logger.error(f"Greška pri zakazivanju zadatka: {e}")
            raise
            
    async def get_task_status(self, task_id: str) -> str:
        """Dohvaća status zadatka."""
        try:
            task_data = self.redis.get(f"task:{task_id}")
            if task_data:
                task = json.loads(task_data)
                return task["status"]
                
            result = self.celery.AsyncResult(task_id)
            if result.ready():
                if result.successful():
                    return "completed"
                else:
                    return "failed"
            elif result.failed():
                return "failed"
            else:
                return "pending"
                
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu statusa zadatka: {e}")
            return "unknown"
            
    async def get_task_result(self, task_id: str) -> Any:
        """Dohvaća rezultat zadatka."""
        try:
            result = self.celery.AsyncResult(task_id)
            
            if result.ready():
                if result.successful():
                    self.stats.completed_tasks += 1
                    self.stats.pending_tasks -= 1
                    return result.get()
                else:
                    self.stats.failed_tasks += 1
                    self.stats.pending_tasks -= 1
                    raise result.result
                    
            return None
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu rezultata zadatka: {e}")
            raise
            
    async def cleanup_old_tasks(self, days: Optional[int] = None) -> None:
        """Čisti zadatke starije od zadano dana."""
        try:
            if days is None:
                days = self.cleanup_days
                
            cutoff_date = datetime.now() - timedelta(days=days)
            pattern = "task:*"
            keys = self.redis.keys(pattern)
            
            for key in keys:
                task_data = self.redis.get(key)
                if task_data:
                    task = json.loads(task_data)
                    if datetime.fromisoformat(task["created_at"]) < cutoff_date:
                        self.redis.delete(key)
                        
            self.celery.control.purge()
            
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju starih zadataka: {e}")
            
    def get_task_metrics(self) -> Dict[str, Any]:
        """Dohvaća metrike zadataka."""
        try:
            return {
                "total_tasks": self.stats.total_tasks,
                "completed_tasks": self.stats.completed_tasks,
                "failed_tasks": self.stats.failed_tasks,
                "pending_tasks": self.stats.pending_tasks,
                "avg_processing_time": self.stats.avg_processing_time,
                "last_error": self.stats.last_error,
                "last_error_time": self.stats.last_error_time,
                "active_workers": len(self.celery.control.inspect().active() or {}),
                "reserved_tasks": len(self.celery.control.inspect().reserved() or {}),
                "scheduled_tasks": len(self.celery.control.inspect().scheduled() or {})
            }
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu metrika zadataka: {e}")
            return {}
            
    def shutdown(self) -> None:
        """Zaustavlja upravljanje asinkronim procesima."""
        try:
            self.celery.close()
            self.redis.close()
        except Exception as e:
            self.logger.error(f"Greška pri zatvaranju upravljanja asinkronim procesima: {e}")
    
    async def process_with_retry(self,
                               func: Callable,
                               *args,
                               max_retries: Optional[int] = None,
                               **kwargs) -> Any:
        """Procesira zadatak s retry logikom"""
        max_retries = max_retries or self.max_retries
        retries = 0
        
        while retries < max_retries:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                retries += 1
                if retries == max_retries:
                    raise
                await asyncio.sleep(2 ** retries)  # Exponential backoff
    
    async def _process_item(self,
                          item: Any,
                          process_func: Callable) -> Any:
        """Procesira pojedinačni item asinkrono"""
        try:
            return await process_func(item)
        except Exception as e:
            logger.error(f"Error processing item: {str(e)}")
            raise
    
    def _generate_task_id(self) -> str:
        """Generira jedinstveni ID zadatka"""
        random_bytes = secrets.token_bytes(16)
        return hashlib.sha256(random_bytes).hexdigest()[:12]
    
    async def cancel_task(self, task_id: str) -> bool:
        """Otkazuje zadatak"""
        try:
            with self._lock:
                if task_id not in self._tasks:
                    return False
                
                task = self._tasks[task_id]
                if task.status in ['pending', 'running']:
                    task.status = 'cancelled'
                    return True
                return False
        except Exception as e:
            logger.error(f"Error cancelling task: {str(e)}")
            return False
    
    async def _delete_task(self, task_id: str):
        """Briše zadatak"""
        try:
            with self._lock:
                if task_id in self._tasks:
                    del self._tasks[task_id]
            
            await self._redis.delete(f'task:{task_id}')
        except Exception as e:
            logger.error(f"Error deleting task: {str(e)}")
    
    async def get_task_metrics(self) -> Dict[str, Any]:
        """Dohvaća metrike zadataka"""
        try:
            with self._lock:
                return {
                    'total_tasks': len(self._tasks),
                    'pending_tasks': sum(1 for t in self._tasks.values() if t.status == 'pending'),
                    'running_tasks': sum(1 for t in self._tasks.values() if t.status == 'running'),
                    'completed_tasks': sum(1 for t in self._tasks.values() if t.status == 'completed'),
                    'failed_tasks': sum(1 for t in self._tasks.values() if t.status == 'failed'),
                    'cancelled_tasks': sum(1 for t in self._tasks.values() if t.status == 'cancelled'),
                    'avg_processing_time': statistics.mean(
                        (t.completed_at - t.started_at).total_seconds()
                        for t in self._tasks.values()
                        if t.status == 'completed' and t.started_at and t.completed_at
                    ) if any(t.status == 'completed' for t in self._tasks.values()) else 0
                }
        except Exception as e:
            logger.error(f"Error getting task metrics: {str(e)}")
            return {}
    
    async def process_with_retry(self,
                               func: Callable,
                               *args,
                               max_retries: Optional[int] = None,
                               **kwargs) -> Any:
        """Procesira zadatak s retry logikom"""
        max_retries = max_retries or self.max_retries
        retries = 0
        
        while retries < max_retries:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                retries += 1
                if retries == max_retries:
                    raise
                await asyncio.sleep(2 ** retries)  # Exponential backoff
    
    def shutdown(self):
        """Zatvara async processor"""
        self._redis.close()
        self._celery.close() 