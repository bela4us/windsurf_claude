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
class EventStats:
    total_events: int = 0
    total_published: int = 0
    total_subscribed: int = 0
    total_handled: int = 0
    total_failed: int = 0
    total_channels: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class EventManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        channel_prefix: str = "event:channel:",
        subscription_prefix: str = "event:subscription:",
        max_channels: int = 1000,
        max_subscribers: int = 100,
        batch_size: int = 100,
        processing_interval: int = 60,  # 1 minuta
        event_timeout: int = 3600  # 1 sat
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.channel_prefix = channel_prefix
        self.subscription_prefix = subscription_prefix
        self.max_channels = max_channels
        self.max_subscribers = max_subscribers
        self.batch_size = batch_size
        self.processing_interval = processing_interval
        self.event_timeout = event_timeout
        
        self.stats = EventStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        self._processing_task: Optional[asyncio.Task] = None
        self._subscribers: Dict[str, List[Callable]] = {}
        
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
                self._process_events()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def create_channel(
        self,
        channel: str
    ) -> bool:
        """Kreira kanal."""
        try:
            # Provjeri broj kanala
            channels = await self._redis.keys(f"{self.channel_prefix}*")
            if len(channels) >= self.max_channels:
                self.logger.warning("Previše kanala")
                return False
                
            # Kreiraj kanal
            channel_key = f"{self.channel_prefix}{channel}"
            await self._redis.sadd(channel_key, "created")
            
            # Ažuriraj statistiku
            self.stats.total_channels += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri kreiranju kanala: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def delete_channel(
        self,
        channel: str
    ) -> bool:
        """Briše kanal."""
        try:
            # Generiraj ključeve
            channel_key = f"{self.channel_prefix}{channel}"
            subscription_key = f"{self.subscription_prefix}{channel}"
            
            # Obriši kanal
            await self._redis.delete(channel_key)
            
            # Obriši pretplate
            await self._redis.delete(subscription_key)
            
            # Ukloni iz lokalnog spremišta
            if channel in self._subscribers:
                del self._subscribers[channel]
                
            # Ažuriraj statistiku
            self.stats.total_channels -= 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri brisanju kanala: {e}")
            return False
            
    async def subscribe(
        self,
        channel: str,
        callback: Callable
    ) -> bool:
        """Pretplaćuje se na kanal."""
        try:
            # Provjeri postojanje kanala
            channel_key = f"{self.channel_prefix}{channel}"
            if not await self._redis.exists(channel_key):
                self.logger.warning(f"Kanal ne postoji: {channel}")
                return False
                
            # Provjeri broj pretplatnika
            subscription_key = f"{self.subscription_prefix}{channel}"
            subscribers = await self._redis.smembers(subscription_key)
            if len(subscribers) >= self.max_subscribers:
                self.logger.warning(f"Previše pretplatnika na kanalu: {channel}")
                return False
                
            # Dodaj pretplatu
            await self._redis.sadd(subscription_key, id(callback))
            
            # Dodaj u lokalno spremište
            if channel not in self._subscribers:
                self._subscribers[channel] = []
            self._subscribers[channel].append(callback)
            
            # Ažuriraj statistiku
            self.stats.total_subscribed += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri pretplati: {e}")
            return False
            
    async def unsubscribe(
        self,
        channel: str,
        callback: Callable
    ) -> bool:
        """Odjavljuje se s kanala."""
        try:
            # Generiraj ključ
            subscription_key = f"{self.subscription_prefix}{channel}"
            
            # Ukloni pretplatu
            await self._redis.srem(subscription_key, id(callback))
            
            # Ukloni iz lokalnog spremišta
            if channel in self._subscribers:
                self._subscribers[channel].remove(callback)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri odjavi: {e}")
            return False
            
    async def publish(
        self,
        channel: str,
        event: Dict[str, Any]
    ) -> bool:
        """Objavljuje događaj."""
        try:
            # Provjeri postojanje kanala
            channel_key = f"{self.channel_prefix}{channel}"
            if not await self._redis.exists(channel_key):
                self.logger.warning(f"Kanal ne postoji: {channel}")
                return False
                
            # Kreiraj događaj
            event_data = {
                "id": f"{channel}:{time.time()}:{id(event)}",
                "channel": channel,
                "data": event,
                "timestamp": time.time()
            }
            
            # Spremi događaj
            await self._redis.lpush(
                channel_key,
                json.dumps(event_data)
            )
            
            # Ažuriraj statistiku
            self.stats.total_events += 1
            self.stats.total_published += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri objavljivanju događaja: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def _process_events(self) -> None:
        """Procesira događaje iz kanala."""
        while True:
            try:
                # Dohvati sve kanale
                channels = await self._redis.keys(f"{self.channel_prefix}*")
                
                for channel_key in channels:
                    # Dohvati batch događaja
                    events = await self._redis.lrange(
                        channel_key,
                        0,
                        self.batch_size - 1
                    )
                    
                    if not events:
                        continue
                        
                    # Procesiraj događaje
                    for event in events:
                        try:
                            # Parsiraj događaj
                            event_data = json.loads(event)
                            
                            # Provjeri timeout
                            if time.time() - event_data["timestamp"] > self.event_timeout:
                                # Ukloni događaj
                                await self._redis.lrem(channel_key, 1, event)
                                continue
                                
                            # Dohvati pretplatnike
                            channel = event_data["channel"]
                            if channel not in self._subscribers:
                                continue
                                
                            # Obavijesti pretplatnike
                            for callback in self._subscribers[channel]:
                                try:
                                    await callback(event_data)
                                    self.stats.total_handled += 1
                                except Exception as e:
                                    self.logger.error(
                                        f"Greška pri obavještavanju pretplatnika: {e}"
                                    )
                                    self.stats.total_failed += 1
                                    
                            # Ukloni događaj
                            await self._redis.lrem(channel_key, 1, event)
                            
                        except Exception as e:
                            self.logger.error(
                                f"Greška pri procesiranju događaja: {e}"
                            )
                            
                # Čekaj sljedeći interval
                await asyncio.sleep(self.processing_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri procesiranju kanala: {e}")
                await asyncio.sleep(self.processing_interval)
                
    def get_stats(self) -> EventStats:
        """Dohvaća statistiku događaja."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje događajima."""
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
class EventStats:
    total_events: int = 0
    total_published: int = 0
    total_subscribed: int = 0
    total_handled: int = 0
    total_failed: int = 0
    total_channels: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class EventManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        channel_prefix: str = "event:channel:",
        subscription_prefix: str = "event:subscription:",
        max_channels: int = 1000,
        max_subscribers: int = 100,
        batch_size: int = 100,
        processing_interval: int = 60,  # 1 minuta
        event_timeout: int = 3600  # 1 sat
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.channel_prefix = channel_prefix
        self.subscription_prefix = subscription_prefix
        self.max_channels = max_channels
        self.max_subscribers = max_subscribers
        self.batch_size = batch_size
        self.processing_interval = processing_interval
        self.event_timeout = event_timeout
        
        self.stats = EventStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        self._processing_task: Optional[asyncio.Task] = None
        self._subscribers: Dict[str, List[Callable]] = {}
        
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
                self._process_events()
            )
            
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji Redis konekcije: {e}")
            raise
            
    async def create_channel(
        self,
        channel: str
    ) -> bool:
        """Kreira kanal."""
        try:
            # Provjeri broj kanala
            channels = await self._redis.keys(f"{self.channel_prefix}*")
            if len(channels) >= self.max_channels:
                self.logger.warning("Previše kanala")
                return False
                
            # Kreiraj kanal
            channel_key = f"{self.channel_prefix}{channel}"
            await self._redis.sadd(channel_key, "created")
            
            # Ažuriraj statistiku
            self.stats.total_channels += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri kreiranju kanala: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def delete_channel(
        self,
        channel: str
    ) -> bool:
        """Briše kanal."""
        try:
            # Generiraj ključeve
            channel_key = f"{self.channel_prefix}{channel}"
            subscription_key = f"{self.subscription_prefix}{channel}"
            
            # Obriši kanal
            await self._redis.delete(channel_key)
            
            # Obriši pretplate
            await self._redis.delete(subscription_key)
            
            # Ukloni iz lokalnog spremišta
            if channel in self._subscribers:
                del self._subscribers[channel]
                
            # Ažuriraj statistiku
            self.stats.total_channels -= 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri brisanju kanala: {e}")
            return False
            
    async def subscribe(
        self,
        channel: str,
        callback: Callable
    ) -> bool:
        """Pretplaćuje se na kanal."""
        try:
            # Provjeri postojanje kanala
            channel_key = f"{self.channel_prefix}{channel}"
            if not await self._redis.exists(channel_key):
                self.logger.warning(f"Kanal ne postoji: {channel}")
                return False
                
            # Provjeri broj pretplatnika
            subscription_key = f"{self.subscription_prefix}{channel}"
            subscribers = await self._redis.smembers(subscription_key)
            if len(subscribers) >= self.max_subscribers:
                self.logger.warning(f"Previše pretplatnika na kanalu: {channel}")
                return False
                
            # Dodaj pretplatu
            await self._redis.sadd(subscription_key, id(callback))
            
            # Dodaj u lokalno spremište
            if channel not in self._subscribers:
                self._subscribers[channel] = []
            self._subscribers[channel].append(callback)
            
            # Ažuriraj statistiku
            self.stats.total_subscribed += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri pretplati: {e}")
            return False
            
    async def unsubscribe(
        self,
        channel: str,
        callback: Callable
    ) -> bool:
        """Odjavljuje se s kanala."""
        try:
            # Generiraj ključ
            subscription_key = f"{self.subscription_prefix}{channel}"
            
            # Ukloni pretplatu
            await self._redis.srem(subscription_key, id(callback))
            
            # Ukloni iz lokalnog spremišta
            if channel in self._subscribers:
                self._subscribers[channel].remove(callback)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri odjavi: {e}")
            return False
            
    async def publish(
        self,
        channel: str,
        event: Dict[str, Any]
    ) -> bool:
        """Objavljuje događaj."""
        try:
            # Provjeri postojanje kanala
            channel_key = f"{self.channel_prefix}{channel}"
            if not await self._redis.exists(channel_key):
                self.logger.warning(f"Kanal ne postoji: {channel}")
                return False
                
            # Kreiraj događaj
            event_data = {
                "id": f"{channel}:{time.time()}:{id(event)}",
                "channel": channel,
                "data": event,
                "timestamp": time.time()
            }
            
            # Spremi događaj
            await self._redis.lpush(
                channel_key,
                json.dumps(event_data)
            )
            
            # Ažuriraj statistiku
            self.stats.total_events += 1
            self.stats.total_published += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri objavljivanju događaja: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return False
            
    async def _process_events(self) -> None:
        """Procesira događaje iz kanala."""
        while True:
            try:
                # Dohvati sve kanale
                channels = await self._redis.keys(f"{self.channel_prefix}*")
                
                for channel_key in channels:
                    # Dohvati batch događaja
                    events = await self._redis.lrange(
                        channel_key,
                        0,
                        self.batch_size - 1
                    )
                    
                    if not events:
                        continue
                        
                    # Procesiraj događaje
                    for event in events:
                        try:
                            # Parsiraj događaj
                            event_data = json.loads(event)
                            
                            # Provjeri timeout
                            if time.time() - event_data["timestamp"] > self.event_timeout:
                                # Ukloni događaj
                                await self._redis.lrem(channel_key, 1, event)
                                continue
                                
                            # Dohvati pretplatnike
                            channel = event_data["channel"]
                            if channel not in self._subscribers:
                                continue
                                
                            # Obavijesti pretplatnike
                            for callback in self._subscribers[channel]:
                                try:
                                    await callback(event_data)
                                    self.stats.total_handled += 1
                                except Exception as e:
                                    self.logger.error(
                                        f"Greška pri obavještavanju pretplatnika: {e}"
                                    )
                                    self.stats.total_failed += 1
                                    
                            # Ukloni događaj
                            await self._redis.lrem(channel_key, 1, event)
                            
                        except Exception as e:
                            self.logger.error(
                                f"Greška pri procesiranju događaja: {e}"
                            )
                            
                # Čekaj sljedeći interval
                await asyncio.sleep(self.processing_interval)
                
            except Exception as e:
                self.logger.error(f"Greška pri procesiranju kanala: {e}")
                await asyncio.sleep(self.processing_interval)
                
    def get_stats(self) -> EventStats:
        """Dohvaća statistiku događaja."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje događajima."""
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
            self.logger.error(f"Greška pri zatvaranju event menadžera: {e}") 