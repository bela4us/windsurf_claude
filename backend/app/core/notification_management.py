<<<<<<< HEAD
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
class NotificationStats:
    total_notifications: int = 0
    total_sent: int = 0
    total_failed: int = 0
    total_queued: int = 0
    total_processed: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class NotificationManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        queue_prefix: str = "notification:queue:",
        sent_prefix: str = "notification:sent:",
        failed_prefix: str = "notification:failed:",
        max_queue_size: int = 10000,
        max_retries: int = 3,
        retry_delay: int = 300,  # 5 minuta
        batch_size: int = 100,
        processing_interval: int = 60  # 1 minuta
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.queue_prefix = queue_prefix
        self.sent_prefix = sent_prefix
        self.failed_prefix = failed_prefix
        self.max_queue_size = max_queue_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.batch_size = batch_size
        self.processing_interval = processing_interval
        
        self.stats = NotificationStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        self._processing_task: Optional[asyncio.Task] = None
        
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
                self._process_notifications()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def send_notification(
        self,
        channel: str,
        message: Dict[str, Any],
        priority: int = 0,
        retry_count: int = 0
    ) -> bool:
        """Šalje notifikaciju."""
        try:
            # Kreiraj notifikaciju
            notification = {
                "timestamp": time.time(),
                "channel": channel,
                "message": message,
                "priority": priority,
                "retry_count": retry_count
            }
            
            # Generiraj ključ
            queue_key = f"{self.queue_prefix}{channel}"
            
            # Provjeri veličinu reda
            queue_size = await self._redis.llen(queue_key)
            if queue_size >= self.max_queue_size:
                self.logger.warning(f"Red notifikacija je pun: {queue_key}")
                return False
                
            # Dodaj u red
            await self._redis.lpush(
                queue_key,
                json.dumps(notification)
            )
            
            # Ažuriraj statistiku
            self.stats.total_notifications += 1
            self.stats.total_queued += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri slanju notifikacije: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def _process_notifications(self) -> None:
        """Procesira notifikacije iz reda."""
        while True:
            try:
                # Dohvati sve kanale
                channels = await self._redis.keys(f"{self.queue_prefix}*")
                
                for channel_key in channels:
                    # Dohvati batch notifikacija
                    notifications = await self._redis.lrange(
                        channel_key,
                        0,
                        self.batch_size - 1
                    )
                    
                    if not notifications:
                        continue
                        
                    # Procesiraj notifikacije
                    for notification in notifications:
                        try:
                            # Parsiraj notifikaciju
                            notification_data = json.loads(notification)
                            
                            # Pokušaj poslati
                            success = await self._send_notification(
                                notification_data
                            )
                            
                            if success:
                                # Označi kao poslano
                                await self._mark_as_sent(
                                    channel_key,
                                    notification
                                )
                            else:
                                # Pokušaj ponovno
                                await self._retry_notification(
                                    channel_key,
                                    notification
                                )
                                
                        except Exception as e:
                            self.logger.error(
                                f"Greška pri procesiranju notifikacije: {e}"
                            )
                            # Označi kao neuspješno
                            await self._mark_as_failed(
                                channel_key,
                                notification,
                                str(e)
                            )
                            
                # Čekaj sljedeći interval
                await asyncio.sleep(self.processing_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri procesiranju reda: {e}")
                await asyncio.sleep(self.processing_interval)
                
    async def _send_notification(
        self,
        notification: Dict[str, Any]
    ) -> bool:
        """Pokušava poslati notifikaciju."""
        try:
            # TODO: Implementirati stvarno slanje
            # Ovo je samo simulacija
            await asyncio.sleep(0.1)
            
            # Ažuriraj statistiku
            self.stats.total_sent += 1
            self.stats.total_processed += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri slanju notifikacije: {e}")
            self.stats.total_failed += 1
            return False
            
    async def _mark_as_sent(
        self,
        queue_key: str,
        notification: str
    ) -> None:
        """Označava notifikaciju kao poslanu."""
        try:
            # Ukloni iz reda
            await self._redis.lrem(queue_key, 1, notification)
            
            # Dodaj u poslane
            sent_key = f"{self.sent_prefix}{queue_key}"
            await self._redis.lpush(sent_key, notification)
            
        except Exception as e:
            self.logger.error(f"Greška pri označavanju kao poslano: {e}")
            
    async def _mark_as_failed(
        self,
        queue_key: str,
        notification: str,
        error: str
    ) -> None:
        """Označava notifikaciju kao neuspješnu."""
        try:
            # Ukloni iz reda
            await self._redis.lrem(queue_key, 1, notification)
            
            # Dodaj u neuspješne
            failed_key = f"{self.failed_prefix}{queue_key}"
            failed_entry = {
                "notification": notification,
                "error": error,
                "timestamp": time.time()
            }
            await self._redis.lpush(
                failed_key,
                json.dumps(failed_entry)
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri označavanju kao neuspješno: {e}")
            
    async def _retry_notification(
        self,
        queue_key: str,
        notification: str
    ) -> None:
        """Pokušava ponovno poslati notifikaciju."""
        try:
            # Parsiraj notifikaciju
            notification_data = json.loads(notification)
            
            # Provjeri broj pokušaja
            if notification_data["retry_count"] >= self.max_retries:
                # Označi kao neuspješno
                await self._mark_as_failed(
                    queue_key,
                    notification,
                    "Previše pokušaja"
                )
                return
                
            # Povećaj broj pokušaja
            notification_data["retry_count"] += 1
            
            # Dodaj nazad u red
            await self._redis.lpush(
                queue_key,
                json.dumps(notification_data)
            )
            
            # Čekaj prije ponovnog pokušaja
            await asyncio.sleep(self.retry_delay)
            
        except Exception as e:
            self.logger.error(f"Greška pri ponovnom pokušaju: {e}")
            
    def get_stats(self) -> NotificationStats:
        """Dohvaća statistiku notifikacija."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje notifikacijama."""
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
=======
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
class NotificationStats:
    total_notifications: int = 0
    total_sent: int = 0
    total_failed: int = 0
    total_queued: int = 0
    total_processed: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class NotificationManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        queue_prefix: str = "notification:queue:",
        sent_prefix: str = "notification:sent:",
        failed_prefix: str = "notification:failed:",
        max_queue_size: int = 10000,
        max_retries: int = 3,
        retry_delay: int = 300,  # 5 minuta
        batch_size: int = 100,
        processing_interval: int = 60  # 1 minuta
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.queue_prefix = queue_prefix
        self.sent_prefix = sent_prefix
        self.failed_prefix = failed_prefix
        self.max_queue_size = max_queue_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.batch_size = batch_size
        self.processing_interval = processing_interval
        
        self.stats = NotificationStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        self._processing_task: Optional[asyncio.Task] = None
        
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
                self._process_notifications()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def send_notification(
        self,
        channel: str,
        message: Dict[str, Any],
        priority: int = 0,
        retry_count: int = 0
    ) -> bool:
        """Šalje notifikaciju."""
        try:
            # Kreiraj notifikaciju
            notification = {
                "timestamp": time.time(),
                "channel": channel,
                "message": message,
                "priority": priority,
                "retry_count": retry_count
            }
            
            # Generiraj ključ
            queue_key = f"{self.queue_prefix}{channel}"
            
            # Provjeri veličinu reda
            queue_size = await self._redis.llen(queue_key)
            if queue_size >= self.max_queue_size:
                self.logger.warning(f"Red notifikacija je pun: {queue_key}")
                return False
                
            # Dodaj u red
            await self._redis.lpush(
                queue_key,
                json.dumps(notification)
            )
            
            # Ažuriraj statistiku
            self.stats.total_notifications += 1
            self.stats.total_queued += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri slanju notifikacije: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def _process_notifications(self) -> None:
        """Procesira notifikacije iz reda."""
        while True:
            try:
                # Dohvati sve kanale
                channels = await self._redis.keys(f"{self.queue_prefix}*")
                
                for channel_key in channels:
                    # Dohvati batch notifikacija
                    notifications = await self._redis.lrange(
                        channel_key,
                        0,
                        self.batch_size - 1
                    )
                    
                    if not notifications:
                        continue
                        
                    # Procesiraj notifikacije
                    for notification in notifications:
                        try:
                            # Parsiraj notifikaciju
                            notification_data = json.loads(notification)
                            
                            # Pokušaj poslati
                            success = await self._send_notification(
                                notification_data
                            )
                            
                            if success:
                                # Označi kao poslano
                                await self._mark_as_sent(
                                    channel_key,
                                    notification
                                )
                            else:
                                # Pokušaj ponovno
                                await self._retry_notification(
                                    channel_key,
                                    notification
                                )
                                
                        except Exception as e:
                            self.logger.error(
                                f"Greška pri procesiranju notifikacije: {e}"
                            )
                            # Označi kao neuspješno
                            await self._mark_as_failed(
                                channel_key,
                                notification,
                                str(e)
                            )
                            
                # Čekaj sljedeći interval
                await asyncio.sleep(self.processing_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri procesiranju reda: {e}")
                await asyncio.sleep(self.processing_interval)
                
    async def _send_notification(
        self,
        notification: Dict[str, Any]
    ) -> bool:
        """Pokušava poslati notifikaciju."""
        try:
            # TODO: Implementirati stvarno slanje
            # Ovo je samo simulacija
            await asyncio.sleep(0.1)
            
            # Ažuriraj statistiku
            self.stats.total_sent += 1
            self.stats.total_processed += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri slanju notifikacije: {e}")
            self.stats.total_failed += 1
            return False
            
    async def _mark_as_sent(
        self,
        queue_key: str,
        notification: str
    ) -> None:
        """Označava notifikaciju kao poslanu."""
        try:
            # Ukloni iz reda
            await self._redis.lrem(queue_key, 1, notification)
            
            # Dodaj u poslane
            sent_key = f"{self.sent_prefix}{queue_key}"
            await self._redis.lpush(sent_key, notification)
            
        except Exception as e:
            self.logger.error(f"Greška pri označavanju kao poslano: {e}")
            
    async def _mark_as_failed(
        self,
        queue_key: str,
        notification: str,
        error: str
    ) -> None:
        """Označava notifikaciju kao neuspješnu."""
        try:
            # Ukloni iz reda
            await self._redis.lrem(queue_key, 1, notification)
            
            # Dodaj u neuspješne
            failed_key = f"{self.failed_prefix}{queue_key}"
            failed_entry = {
                "notification": notification,
                "error": error,
                "timestamp": time.time()
            }
            await self._redis.lpush(
                failed_key,
                json.dumps(failed_entry)
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri označavanju kao neuspješno: {e}")
            
    async def _retry_notification(
        self,
        queue_key: str,
        notification: str
    ) -> None:
        """Pokušava ponovno poslati notifikaciju."""
        try:
            # Parsiraj notifikaciju
            notification_data = json.loads(notification)
            
            # Provjeri broj pokušaja
            if notification_data["retry_count"] >= self.max_retries:
                # Označi kao neuspješno
                await self._mark_as_failed(
                    queue_key,
                    notification,
                    "Previše pokušaja"
                )
                return
                
            # Povećaj broj pokušaja
            notification_data["retry_count"] += 1
            
            # Dodaj nazad u red
            await self._redis.lpush(
                queue_key,
                json.dumps(notification_data)
            )
            
            # Čekaj prije ponovnog pokušaja
            await asyncio.sleep(self.retry_delay)
            
        except Exception as e:
            self.logger.error(f"Greška pri ponovnom pokušaju: {e}")
            
    def get_stats(self) -> NotificationStats:
        """Dohvaća statistiku notifikacija."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje notifikacijama."""
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
>>>>>>> c45eb88e3e23e6f6a3bf252c5a572f1c5cdb8266
            self.logger.error(f"Greška pri zatvaranju notification menadžera: {e}") 