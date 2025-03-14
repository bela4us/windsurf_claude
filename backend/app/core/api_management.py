<<<<<<< HEAD
from typing import Dict, Any, Optional, List, Callable, Union, TypeVar, Generic
import asyncio
import json
import threading
from datetime import datetime
from dataclasses import dataclass
import logging
from pathlib import Path
import aiohttp
import orjson
import time
from functools import wraps
import ssl
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
import backoff
import circuitbreaker
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class APIStats:
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    total_bytes: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class APIManager:
    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
        circuit_breaker_reset_timeout: float = 300.0,
        max_connections: int = 100,
        max_connections_per_host: int = 10,
        ttl: int = 300,  # 5 minuta
        compression_threshold: int = 1024  # 1KB
    ):
        self.logger = logging.getLogger(__name__)
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.circuit_breaker_reset_timeout = circuit_breaker_reset_timeout
        self.max_connections = max_connections
        self.max_connections_per_host = max_connections_per_host
        self.ttl = ttl
        self.compression_threshold = compression_threshold
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.stats = APIStats()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Inicijalizira aiohttp sesiju."""
        try:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                connector=aiohttp.TCPConnector(
                    limit=self.max_connections,
                    limit_per_host=self.max_connections_per_host,
                    ttl_dns_cache=300,
                    use_dns_cache=True
                )
            )
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji aiohttp sesije: {e}")
            raise
            
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def request(self,
                     method: str,
                     endpoint: str,
                     params: Optional[Dict[str, Any]] = None,
                     data: Optional[Dict[str, Any]] = None,
                     headers: Optional[Dict[str, str]] = None,
                     timeout: Optional[float] = None) -> Dict[str, Any]:
        """Izvršava API zahtjev"""
        try:
            if not self.session:
                await self.initialize()
            
            url = f"{endpoint}"
            start_time = time.time()
            
            async with self.session.request(
                method,
                url,
                params=params,
                json=data,
                headers=headers,
                timeout=timeout or self.timeout
            ) as response:
                response.raise_for_status()
                response_data = await response.json()
                
                # Ažuriraj statistiku
                with self._lock:
                    self.stats.total_requests += 1
                    if response.status < 400:
                        self.stats.successful_requests += 1
                    else:
                        self.stats.failed_requests += 1
                        self.stats.last_error = str(response_data)
                        self.stats.last_error_time = datetime.now()
                    
                    # Ažuriraj prosječno vrijeme odgovora
                    response_time = time.time() - start_time
                    self.stats.avg_response_time = (
                        (self.stats.avg_response_time * (self.stats.total_requests - 1) +
                         response_time) / self.stats.total_requests
                    )
                
                if response.status >= 400:
                    raise aiohttp.ClientError(f"API request failed: {response_data}")
                
                return response_data
        except Exception as e:
            logger.error(f"Error making API request: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    @circuit(
        failure_threshold=5,
        recovery_timeout=60,
        reset_timeout=300
    )
    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        cache: bool = True
    ) -> Dict[str, Any]:
        """Izvršava GET zahtjev."""
        try:
            cache_key = f"GET:{url}:{json.dumps(params or {})}"
            
            if cache and cache_key in self._cache:
                cached_data = self._cache[cache_key]
                if time.time() - cached_data["timestamp"] < self.ttl:
                    return cached_data["data"]
                    
            start_time = time.time()
            
            response_data = await self.request('GET', url, params=params, headers=headers)
            
            response_time = time.time() - start_time
            
            if cache:
                async with self._lock:
                    self._cache[cache_key] = {
                        "data": response_data,
                        "timestamp": time.time()
                    }
                    
            self._update_stats(True, response_time, len(str(response_data)))
            return response_data
            
        except Exception as e:
            self._update_stats(False, 0, 0, str(e))
            raise
            
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    @circuit(
        failure_threshold=5,
        recovery_timeout=60,
        reset_timeout=300
    )
    async def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Izvršava POST zahtjev."""
        try:
            start_time = time.time()
            
            response_data = await self.request('POST', url, data=data, json=json_data, headers=headers)
            
            response_time = time.time() - start_time
            self._update_stats(True, response_time, len(str(response_data)))
            return response_data
            
        except Exception as e:
            self._update_stats(False, 0, 0, str(e))
            raise
            
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    @circuit(
        failure_threshold=5,
        recovery_timeout=60,
        reset_timeout=300
    )
    async def put(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Izvršava PUT zahtjev."""
        try:
            start_time = time.time()
            
            response_data = await self.request('PUT', url, data=data, json=json_data, headers=headers)
            
            response_time = time.time() - start_time
            self._update_stats(True, response_time, len(str(response_data)))
            return response_data
            
        except Exception as e:
            self._update_stats(False, 0, 0, str(e))
            raise
            
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    @circuit(
        failure_threshold=5,
        recovery_timeout=60,
        reset_timeout=300
    )
    async def delete(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Izvršava DELETE zahtjev."""
        try:
            start_time = time.time()
            
            response_data = await self.request('DELETE', url, headers=headers)
            
            response_time = time.time() - start_time
            self._update_stats(True, response_time, len(str(response_data)))
            return response_data
            
        except Exception as e:
            self._update_stats(False, 0, 0, str(e))
            raise
            
    async def batch_request(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Izvršava batch zahtjeve."""
        try:
            tasks = []
            
            for request in requests:
                method = request["method"]
                url = request["url"]
                params = request.get("params")
                data = request.get("data")
                json_data = request.get("json")
                headers = request.get("headers")
                
                if method == "GET":
                    task = self.get(url, params, headers)
                elif method == "POST":
                    task = self.post(url, data, json_data, headers)
                elif method == "PUT":
                    task = self.put(url, data, json_data, headers)
                elif method == "DELETE":
                    task = self.delete(url, headers)
                else:
                    raise ValueError(f"Nepodržana metoda: {method}")
                    
                tasks.append(task)
                
            return await asyncio.gather(*tasks)
            
        except Exception as e:
            self.logger.error(f"Greška pri batch zahtjevima: {e}")
            raise
            
    def _update_stats(
        self,
        success: bool,
        response_time: float,
        bytes_sent: int,
        error: Optional[str] = None
    ) -> None:
        """Ažurira statistiku."""
        self.stats.total_requests += 1
        
        if success:
            self.stats.successful_requests += 1
            self.stats.avg_response_time = (
                (self.stats.avg_response_time * (self.stats.total_requests - 1) +
                 response_time) / self.stats.total_requests
            )
        else:
            self.stats.failed_requests += 1
            self.stats.last_error = error
            self.stats.last_error_time = datetime.now()
            
        self.stats.total_bytes += bytes_sent
        
    def get_stats(self) -> APIStats:
        """Dohvaća statistiku API poziva."""
        return self.stats
        
    async def cleanup(self) -> None:
        """Čisti cache."""
        try:
            current_time = time.time()
            expired_keys = []
            
            for key, value in self._cache.items():
                if current_time - value["timestamp"] > self.ttl:
                    expired_keys.append(key)
                    
            for key in expired_keys:
                del self._cache[key]
                
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju cachea: {e}")
            
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje API pozivima."""
        try:
            if self.session:
                await self.session.close()
        except Exception as e:
=======
from typing import Dict, Any, Optional, List, Callable, Union, TypeVar, Generic
import asyncio
import json
import threading
from datetime import datetime
from dataclasses import dataclass
import logging
from pathlib import Path
import aiohttp
import orjson
import time
from functools import wraps
import ssl
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
import backoff
import circuitbreaker
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class APIStats:
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    total_bytes: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class APIManager:
    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
        circuit_breaker_reset_timeout: float = 300.0,
        max_connections: int = 100,
        max_connections_per_host: int = 10,
        ttl: int = 300,  # 5 minuta
        compression_threshold: int = 1024  # 1KB
    ):
        self.logger = logging.getLogger(__name__)
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.circuit_breaker_reset_timeout = circuit_breaker_reset_timeout
        self.max_connections = max_connections
        self.max_connections_per_host = max_connections_per_host
        self.ttl = ttl
        self.compression_threshold = compression_threshold
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.stats = APIStats()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Inicijalizira aiohttp sesiju."""
        try:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                connector=aiohttp.TCPConnector(
                    limit=self.max_connections,
                    limit_per_host=self.max_connections_per_host,
                    ttl_dns_cache=300,
                    use_dns_cache=True
                )
            )
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji aiohttp sesije: {e}")
            raise
            
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def request(self,
                     method: str,
                     endpoint: str,
                     params: Optional[Dict[str, Any]] = None,
                     data: Optional[Dict[str, Any]] = None,
                     headers: Optional[Dict[str, str]] = None,
                     timeout: Optional[float] = None) -> Dict[str, Any]:
        """Izvršava API zahtjev"""
        try:
            if not self.session:
                await self.initialize()
            
            url = f"{endpoint}"
            start_time = time.time()
            
            async with self.session.request(
                method,
                url,
                params=params,
                json=data,
                headers=headers,
                timeout=timeout or self.timeout
            ) as response:
                response.raise_for_status()
                response_data = await response.json()
                
                # Ažuriraj statistiku
                with self._lock:
                    self.stats.total_requests += 1
                    if response.status < 400:
                        self.stats.successful_requests += 1
                    else:
                        self.stats.failed_requests += 1
                        self.stats.last_error = str(response_data)
                        self.stats.last_error_time = datetime.now()
                    
                    # Ažuriraj prosječno vrijeme odgovora
                    response_time = time.time() - start_time
                    self.stats.avg_response_time = (
                        (self.stats.avg_response_time * (self.stats.total_requests - 1) +
                         response_time) / self.stats.total_requests
                    )
                
                if response.status >= 400:
                    raise aiohttp.ClientError(f"API request failed: {response_data}")
                
                return response_data
        except Exception as e:
            logger.error(f"Error making API request: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    @circuit(
        failure_threshold=5,
        recovery_timeout=60,
        reset_timeout=300
    )
    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        cache: bool = True
    ) -> Dict[str, Any]:
        """Izvršava GET zahtjev."""
        try:
            cache_key = f"GET:{url}:{json.dumps(params or {})}"
            
            if cache and cache_key in self._cache:
                cached_data = self._cache[cache_key]
                if time.time() - cached_data["timestamp"] < self.ttl:
                    return cached_data["data"]
                    
            start_time = time.time()
            
            response_data = await self.request('GET', url, params=params, headers=headers)
            
            response_time = time.time() - start_time
            
            if cache:
                async with self._lock:
                    self._cache[cache_key] = {
                        "data": response_data,
                        "timestamp": time.time()
                    }
                    
            self._update_stats(True, response_time, len(str(response_data)))
            return response_data
            
        except Exception as e:
            self._update_stats(False, 0, 0, str(e))
            raise
            
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    @circuit(
        failure_threshold=5,
        recovery_timeout=60,
        reset_timeout=300
    )
    async def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Izvršava POST zahtjev."""
        try:
            start_time = time.time()
            
            response_data = await self.request('POST', url, data=data, json=json_data, headers=headers)
            
            response_time = time.time() - start_time
            self._update_stats(True, response_time, len(str(response_data)))
            return response_data
            
        except Exception as e:
            self._update_stats(False, 0, 0, str(e))
            raise
            
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    @circuit(
        failure_threshold=5,
        recovery_timeout=60,
        reset_timeout=300
    )
    async def put(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Izvršava PUT zahtjev."""
        try:
            start_time = time.time()
            
            response_data = await self.request('PUT', url, data=data, json=json_data, headers=headers)
            
            response_time = time.time() - start_time
            self._update_stats(True, response_time, len(str(response_data)))
            return response_data
            
        except Exception as e:
            self._update_stats(False, 0, 0, str(e))
            raise
            
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    @circuit(
        failure_threshold=5,
        recovery_timeout=60,
        reset_timeout=300
    )
    async def delete(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Izvršava DELETE zahtjev."""
        try:
            start_time = time.time()
            
            response_data = await self.request('DELETE', url, headers=headers)
            
            response_time = time.time() - start_time
            self._update_stats(True, response_time, len(str(response_data)))
            return response_data
            
        except Exception as e:
            self._update_stats(False, 0, 0, str(e))
            raise
            
    async def batch_request(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Izvršava batch zahtjeve."""
        try:
            tasks = []
            
            for request in requests:
                method = request["method"]
                url = request["url"]
                params = request.get("params")
                data = request.get("data")
                json_data = request.get("json")
                headers = request.get("headers")
                
                if method == "GET":
                    task = self.get(url, params, headers)
                elif method == "POST":
                    task = self.post(url, data, json_data, headers)
                elif method == "PUT":
                    task = self.put(url, data, json_data, headers)
                elif method == "DELETE":
                    task = self.delete(url, headers)
                else:
                    raise ValueError(f"Nepodržana metoda: {method}")
                    
                tasks.append(task)
                
            return await asyncio.gather(*tasks)
            
        except Exception as e:
            self.logger.error(f"Greška pri batch zahtjevima: {e}")
            raise
            
    def _update_stats(
        self,
        success: bool,
        response_time: float,
        bytes_sent: int,
        error: Optional[str] = None
    ) -> None:
        """Ažurira statistiku."""
        self.stats.total_requests += 1
        
        if success:
            self.stats.successful_requests += 1
            self.stats.avg_response_time = (
                (self.stats.avg_response_time * (self.stats.total_requests - 1) +
                 response_time) / self.stats.total_requests
            )
        else:
            self.stats.failed_requests += 1
            self.stats.last_error = error
            self.stats.last_error_time = datetime.now()
            
        self.stats.total_bytes += bytes_sent
        
    def get_stats(self) -> APIStats:
        """Dohvaća statistiku API poziva."""
        return self.stats
        
    async def cleanup(self) -> None:
        """Čisti cache."""
        try:
            current_time = time.time()
            expired_keys = []
            
            for key, value in self._cache.items():
                if current_time - value["timestamp"] > self.ttl:
                    expired_keys.append(key)
                    
            for key in expired_keys:
                del self._cache[key]
                
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju cachea: {e}")
            
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje API pozivima."""
        try:
            if self.session:
                await self.session.close()
        except Exception as e:
>>>>>>> c45eb88e3e23e6f6a3bf252c5a572f1c5cdb8266
            self.logger.error(f"Greška pri zatvaranju API menadžera: {e}") 