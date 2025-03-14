from typing import Dict, Any, Optional, List, Union, Type, Callable
import logging
import asyncio
import time
import json
from datetime import datetime
from dataclasses import dataclass
from redis import Redis
from aioredis import Redis as AsyncRedis

@dataclass
class TaskStats:
    total_tasks: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_cancelled: int = 0
    total_running: int = 0
    total_queued: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class TaskManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        queue_prefix: str = "task:queue:",
        running_prefix: str = "task:running:",
        completed_prefix: str = "task:completed:",
        failed_prefix: str = "task:failed:",
        cancelled_prefix: str = "task:cancelled:",
        max_queue_size: int = 10000,
        max_workers: int = 10,
        batch_size: int = 100,
        processing_interval: int = 60,  # 1 minuta
        task_timeout: int = 3600  # 1 sat
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.queue_prefix = queue_prefix
        self.running_prefix = running_prefix
        self.completed_prefix = completed_prefix
        self.failed_prefix = failed_prefix
        self.cancelled_prefix = cancelled_prefix
        self.max_queue_size = max_queue_size
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.processing_interval = processing_interval
        self.task_timeout = task_timeout
        
        self.stats = TaskStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        self._processing_task: Optional[asyncio.Task] = None
        self._workers: List[asyncio.Task] = []
        
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
                self._process_tasks()
            )
            
            # Pokreni workere
            for _ in range(self.max_workers):
                worker = asyncio.create_task(
                    self._worker_loop()
                )
                self._workers.append(worker)
                
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def submit_task(
        self,
        task_type: str,
        data: Dict[str, Any],
        priority: int = 0
    ) -> Optional[str]:
        """Šalje zadatak."""
        try:
            # Kreiraj zadatak
            task = {
                "id": f"{task_type}:{time.time()}:{id(data)}",
                "type": task_type,
                "data": data,
                "priority": priority,
                "status": "queued",
                "created_at": time.time(),
                "updated_at": time.time()
            }
            
            # Generiraj ključ
            queue_key = f"{self.queue_prefix}{task_type}"
            
            # Provjeri veličinu reda
            queue_size = await self._redis.llen(queue_key)
            if queue_size >= self.max_queue_size:
                self.logger.warning(f"Red zadataka je pun: {queue_key}")
                return None
                
            # Dodaj u red
            await self._redis.lpush(
                queue_key,
                json.dumps(task)
            )
            
            # Ažuriraj statistiku
            self.stats.total_tasks += 1
            self.stats.total_queued += 1
            
            return task["id"]
            
        except Exception as e:
            self.logger.error(f"Greška pri slanju zadatka: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return None
            
    async def _process_tasks(self) -> None:
        """Procesira zadatke iz reda."""
        while True:
            try:
                # Dohvati sve tipove
                types = await self._redis.keys(f"{self.queue_prefix}*")
                
                for type_key in types:
                    # Dohvati batch zadataka
                    tasks = await self._redis.lrange(
                        type_key,
                        0,
                        self.batch_size - 1
                    )
                    
                    if not tasks:
                        continue
                        
                    # Procesiraj zadatke
                    for task in tasks:
                        try:
                            # Parsiraj zadatak
                            task_data = json.loads(task)
                            
                            # Provjeri status
                            if task_data["status"] != "queued":
                                continue
                                
                            # Provjeri timeout
                            if time.time() - task_data["created_at"] > self.task_timeout:
                                # Označi kao neuspješno
                                await self._mark_as_failed(
                                    type_key,
                                    task,
                                    "Timeout"
                                )
                                continue
                                
                            # Označi kao pokrenuto
                            await self._mark_as_running(
                                type_key,
                                task
                            )
                            
                        except Exception as e:
                            self.logger.error(
                                f"Greška pri procesiranju zadatka: {e}"
                            )
                            # Označi kao neuspješno
                            await self._mark_as_failed(
                                type_key,
                                task,
                                str(e)
                            )
                            
                # Čekaj sljedeći interval
                await asyncio.sleep(self.processing_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri procesiranju reda: {e}")
                await asyncio.sleep(self.processing_interval)
                
    async def _worker_loop(self) -> None:
        """Petlja za workere."""
        while True:
            try:
                # Dohvati sve tipove
                types = await self._redis.keys(f"{self.running_prefix}*")
                
                for type_key in types:
                    # Dohvati batch zadataka
                    tasks = await self._redis.lrange(
                        type_key,
                        0,
                        self.batch_size - 1
                    )
                    
                    if not tasks:
                        continue
                        
                    # Procesiraj zadatke
                    for task in tasks:
                        try:
                            # Parsiraj zadatak
                            task_data = json.loads(task)
                            
                            # Provjeri status
                            if task_data["status"] != "running":
                                continue
                                
                            # Provjeri timeout
                            if time.time() - task_data["updated_at"] > self.task_timeout:
                                # Označi kao neuspješno
                                await self._mark_as_failed(
                                    type_key,
                                    task,
                                    "Timeout"
                                )
                                continue
                                
                            # Izvrši zadatak
                            success = await self._execute_task(
                                task_data
                            )
                            
                            if success:
                                # Označi kao završeno
                                await self._mark_as_completed(
                                    type_key,
                                    task
                                )
                            else:
                                # Označi kao neuspješno
                                await self._mark_as_failed(
                                    type_key,
                                    task,
                                    "Execution failed"
                                )
                                
                        except Exception as e:
                            self.logger.error(
                                f"Greška pri izvršavanju zadatka: {e}"
                            )
                            # Označi kao neuspješno
                            await self._mark_as_failed(
                                type_key,
                                task,
                                str(e)
                            )
                            
                # Čekaj sljedeći interval
                await asyncio.sleep(self.processing_interval)
                
            except Exception as e:
                self.logger.error(f"Greška u worker petlji: {e}")
                await asyncio.sleep(self.processing_interval)
                
    async def _execute_task(
        self,
        task: Dict[str, Any]
    ) -> bool:
        """Izvršava zadatak."""
        try:
            # TODO: Implementirati stvarno izvršavanje
            # Ovo je samo simulacija
            await asyncio.sleep(0.1)
            
            # Ažuriraj statistiku
            self.stats.total_completed += 1
            self.stats.total_running -= 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri izvršavanju zadatka: {e}")
            self.stats.total_failed += 1
            self.stats.total_running -= 1
            return False
            
    async def _mark_as_running(
        self,
        queue_key: str,
        task: str
    ) -> None:
        """Označava zadatak kao pokrenut."""
        try:
            # Ukloni iz reda
            await self._redis.lrem(queue_key, 1, task)
            
            # Dodaj u pokrenute
            running_key = f"{self.running_prefix}{queue_key}"
            await self._redis.lpush(running_key, task)
            
            # Ažuriraj statistiku
            self.stats.total_queued -= 1
            self.stats.total_running += 1
            
        except Exception as e:
            self.logger.error(f"Greška pri označavanju kao pokrenuto: {e}")
            
    async def _mark_as_completed(
        self,
        running_key: str,
        task: str
    ) -> None:
        """Označava zadatak kao završen."""
        try:
            # Ukloni iz pokrenutih
            await self._redis.lrem(running_key, 1, task)
            
            # Dodaj u završene
            completed_key = f"{self.completed_prefix}{running_key}"
            await self._redis.lpush(completed_key, task)
            
        except Exception as e:
            self.logger.error(f"Greška pri označavanju kao završeno: {e}")
            
    async def _mark_as_failed(
        self,
        key: str,
        task: str,
        error: str
    ) -> None:
        """Označava zadatak kao neuspješan."""
        try:
            # Ukloni iz trenutnog stanja
            await self._redis.lrem(key, 1, task)
            
            # Dodaj u neuspješne
            failed_key = f"{self.failed_prefix}{key}"
            failed_entry = {
                "task": task,
                "error": error,
                "timestamp": time.time()
            }
            await self._redis.lpush(
                failed_key,
                json.dumps(failed_entry)
            )
            
            # Ažuriraj statistiku
            self.stats.total_failed += 1
            if "running" in key:
                self.stats.total_running -= 1
            elif "queued" in key:
                self.stats.total_queued -= 1
            
        except Exception as e:
            self.logger.error(f"Greška pri označavanju kao neuspješno: {e}")
            
    async def cancel_task(
        self,
        task_id: str
    ) -> bool:
        """Otkazuje zadatak."""
        try:
            # Dohvati sve tipove
            types = await self._redis.keys(f"{self.running_prefix}*")
            
            for type_key in types:
                # Dohvati zadatke
                tasks = await self._redis.lrange(type_key, 0, -1)
                
                for task in tasks:
                    # Parsiraj zadatak
                    task_data = json.loads(task)
                    
                    # Provjeri ID
                    if task_data["id"] == task_id:
                        # Označi kao otkazano
                        await self._mark_as_cancelled(
                            type_key,
                            task
                        )
                        return True
                        
            return False
            
        except Exception as e:
            self.logger.error(f"Greška pri otkazivanju zadatka: {e}")
            return False
            
    async def _mark_as_cancelled(
        self,
        key: str,
        task: str
    ) -> None:
        """Označava zadatak kao otkazan."""
        try:
            # Ukloni iz trenutnog stanja
            await self._redis.lrem(key, 1, task)
            
            # Dodaj u otkazane
            cancelled_key = f"{self.cancelled_prefix}{key}"
            await self._redis.lpush(cancelled_key, task)
            
            # Ažuriraj statistiku
            self.stats.total_cancelled += 1
            if "running" in key:
                self.stats.total_running -= 1
            elif "queued" in key:
                self.stats.total_queued -= 1
            
        except Exception as e:
            self.logger.error(f"Greška pri označavanju kao otkazano: {e}")
            
    def get_stats(self) -> TaskStats:
        """Dohvaća statistiku zadataka."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje zadacima."""
        try:
            # Zaustavi procesiranje
            if self._processing_task:
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass
                    
            # Zaustavi workere
            for worker in self._workers:
                worker.cancel()
                try:
                    await worker
                except asyncio.CancelledError:
                    pass
                    
            # Zatvori Redis
            if self._redis:
                await self._redis.close()
                
        except Exception as e:
            self.logger.error(f"Greška pri zatvaranju task menadžera: {e}") 