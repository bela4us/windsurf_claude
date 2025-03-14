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
class MetricStats:
    total_metrics: int = 0
    total_values: int = 0
    total_series: int = 0
    total_alerts: int = 0
    total_notifications: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class MetricsManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        metric_prefix: str = "metric:",
        series_prefix: str = "series:",
        alert_prefix: str = "alert:",
        max_points: int = 1000,
        retention_days: int = 30,
        aggregation_window: int = 3600,  # 1 sat
        alert_threshold: float = 0.0,
        alert_window: int = 300  # 5 minuta
    ):
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url
        self.metric_prefix = metric_prefix
        self.series_prefix = series_prefix
        self.alert_prefix = alert_prefix
        self.max_points = max_points
        self.retention_days = retention_days
        self.aggregation_window = aggregation_window
        self.alert_threshold = alert_threshold
        self.alert_window = alert_window
        
        self.stats = MetricStats()
        self._redis: Optional[AsyncRedis] = None
        self._lock = asyncio.Lock()
        
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
            
    async def record_metric(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Bilježi metriku."""
        try:
            # Kreiraj metric entry
            metric_entry = {
                "timestamp": time.time(),
                "value": value,
                "tags": tags or {}
            }
            
            # Generiraj ključeve
            metric_key = f"{self.metric_prefix}{name}"
            series_key = f"{self.series_prefix}{name}"
            
            # Spremi metriku
            await self._redis.lpush(
                metric_key,
                json.dumps(metric_entry)
            )
            
            # Održavaj maksimalni broj točaka
            await self._redis.ltrim(metric_key, 0, self.max_points - 1)
            
            # Dodaj u seriju
            await self._redis.zadd(
                series_key,
                {json.dumps(metric_entry): time.time()}
            )
            
            # Ažuriraj statistiku
            self.stats.total_metrics += 1
            self.stats.total_values += 1
            
            # Provjeri alert
            await self._check_alert(name, value)
            
        except Exception as e:
            self.logger.error(f"Greška pri bilježenju metrike: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            
    async def get_metric(
        self,
        name: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Dohvaća metriku."""
        try:
            if not self._redis:
                return []
                
            # Generiraj ključ
            metric_key = f"{self.metric_prefix}{name}"
            
            # Dohvati točke
            points = await self._redis.lrange(metric_key, 0, limit - 1)
            
            # Parsiraj točke
            metrics = []
            for point in points:
                metric = json.loads(point)
                
                # Filtriraj po vremenu
                if start_time and metric["timestamp"] < start_time:
                    continue
                if end_time and metric["timestamp"] > end_time:
                    continue
                    
                metrics.append(metric)
                
            return metrics
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu metrike: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return []
            
    async def get_series(
        self,
        name: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        aggregation: str = "avg"
    ) -> List[Dict[str, Any]]:
        """Dohvaća seriju metrike."""
        try:
            if not self._redis:
                return []
                
            # Generiraj ključ
            series_key = f"{self.series_prefix}{name}"
            
            # Dohvati točke
            points = await self._redis.zrangebyscore(
                series_key,
                start_time or 0,
                end_time or float("inf")
            )
            
            # Parsiraj točke
            series = []
            for point in points:
                metric = json.loads(point)
                series.append(metric)
                
            # Agregiraj ako je potrebno
            if aggregation != "none":
                series = await self._aggregate_series(series, aggregation)
                
            return series
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu serije: {e}")
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            return []
            
    async def _aggregate_series(
        self,
        series: List[Dict[str, Any]],
        aggregation: str
    ) -> List[Dict[str, Any]]:
        """Agregira seriju."""
        try:
            if not series:
                return []
                
            # Sortiraj po vremenu
            series.sort(key=lambda x: x["timestamp"])
            
            # Agregiraj po prozoru
            window_size = self.aggregation_window
            aggregated = []
            
            current_window = []
            window_start = series[0]["timestamp"]
            
            for point in series:
                if point["timestamp"] - window_start > window_size:
                    # Agregiraj trenutni prozor
                    if current_window:
                        aggregated.append({
                            "timestamp": window_start,
                            "value": self._aggregate_values(
                                [p["value"] for p in current_window],
                                aggregation
                            ),
                            "tags": current_window[0]["tags"]
                        })
                        
                    # Započni novi prozor
                    current_window = []
                    window_start = point["timestamp"]
                    
                current_window.append(point)
                
            # Agregiraj zadnji prozor
            if current_window:
                aggregated.append({
                    "timestamp": window_start,
                    "value": self._aggregate_values(
                        [p["value"] for p in current_window],
                        aggregation
                    ),
                    "tags": current_window[0]["tags"]
                })
                
            return aggregated
            
        except Exception as e:
            self.logger.error(f"Greška pri agregaciji serije: {e}")
            return series
            
    def _aggregate_values(
        self,
        values: List[float],
        aggregation: str
    ) -> float:
        """Agregira vrijednosti."""
        try:
            if not values:
                return 0.0
                
            if aggregation == "avg":
                return sum(values) / len(values)
            elif aggregation == "min":
                return min(values)
            elif aggregation == "max":
                return max(values)
            elif aggregation == "sum":
                return sum(values)
            else:
                return sum(values) / len(values)
                
        except Exception as e:
            self.logger.error(f"Greška pri agregaciji vrijednosti: {e}")
            return 0.0
            
    async def _check_alert(
        self,
        name: str,
        value: float
    ) -> None:
        """Provjerava alert."""
        try:
            if value > self.alert_threshold:
                # Kreiraj alert
                alert_entry = {
                    "timestamp": time.time(),
                    "metric": name,
                    "value": value,
                    "threshold": self.alert_threshold
                }
                
                # Spremi alert
                alert_key = f"{self.alert_prefix}{name}"
                await self._redis.lpush(
                    alert_key,
                    json.dumps(alert_entry)
                )
                
                # Održavaj maksimalni broj alertova
                await self._redis.ltrim(alert_key, 0, self.max_points - 1)
                
                # Ažuriraj statistiku
                self.stats.total_alerts += 1
                
                # TODO: Implementirati notifikacije
                
        except Exception as e:
            self.logger.error(f"Greška pri provjeri alerta: {e}")
            
    def get_stats(self) -> MetricStats:
        """Dohvaća statistiku metrika."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje metrikama."""
        try:
            if self._redis:
                await self._redis.close()
        except Exception as e:
            self.logger.error(f"Greška pri zatvaranju metrics menadžera: {e}") 