from typing import Dict, List, Optional, Any, Callable, Union
import asyncio
import aiohttp
import logging
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta
import ssl
import socket
from dataclasses import dataclass
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import threading

logger = logging.getLogger(__name__)

@dataclass
class ConnectionStats:
    total_connections: int = 0
    active_connections: int = 0
    failed_connections: int = 0
    avg_response_time: float = 0.0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class ConnectionPool:
    def __init__(
        self,
        max_connections: int = 100,
        max_retries: int = 3,
        timeout: float = 30.0,
        ssl_verify: bool = True,
        ssl_cert: Optional[str] = None,
        ssl_key: Optional[str] = None,
        keepalive_timeout: float = 60.0,
        max_redirects: int = 5
    ):
        self.logger = logging.getLogger(__name__)
        self.max_connections = max_connections
        self.max_retries = max_retries
        self.timeout = timeout
        self.ssl_verify = ssl_verify
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.keepalive_timeout = keepalive_timeout
        self.max_redirects = max_redirects
        
        self.sessions: Dict[str, aiohttp.ClientSession] = {}
        self.stats = ConnectionStats()
        self._lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Inicijalizira connection pool."""
        try:
            await self._cleanup_connections()
        except Exception as e:
            self.logger.error(f"Greška pri inicijalizaciji connection pool-a: {e}")
            
    async def shutdown(self) -> None:
        """Zaustavlja connection pool."""
        try:
            for session in self.sessions.values():
                await session.close()
            self.sessions.clear()
        except Exception as e:
            self.logger.error(f"Greška pri zatvaranju connection pool-a: {e}")
            
    @asynccontextmanager
    async def get_session(self, base_url: str) -> aiohttp.ClientSession:
        """Dohvaća ili kreira novu sesiju za dani base URL."""
        try:
            if base_url not in self.sessions:
                self.sessions[base_url] = await self._create_session()
                
            session = self.sessions[base_url]
            self.stats.active_connections += 1
            
            try:
                yield session
            finally:
                self.stats.active_connections -= 1
                
        except Exception as e:
            self.stats.failed_connections += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = datetime.now()
            raise
            
    async def _create_session(self) -> aiohttp.ClientSession:
        """Kreira novu aiohttp sesiju."""
        ssl_context = None
        if self.ssl_verify:
            ssl_context = ssl.create_default_context()
            if self.ssl_cert and self.ssl_key:
                ssl_context.load_cert_chain(self.ssl_cert, self.ssl_key)
                
        return aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            connector=aiohttp.TCPConnector(
                limit=self.max_connections,
                ssl=ssl_context,
                keepalive_timeout=self.keepalive_timeout,
                max_redirects=self.max_redirects
            )
        )
        
    async def _cleanup_connections(self) -> None:
        """Čisti neaktivne konekcije."""
        try:
            async with self._lock:
                for base_url, session in list(self.sessions.items()):
                    if session.closed:
                        del self.sessions[base_url]
                        
        except Exception as e:
            self.logger.error(f"Greška pri čišćenju konekcija: {e}")
            
    async def make_request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Any:
        """Izvršava HTTP zahtjev s retry logikom."""
        start_time = time.time()
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                async with self.get_session(url) as session:
                    async with session.request(method, url, **kwargs) as response:
                        response_time = time.time() - start_time
                        self.stats.avg_response_time = (
                            (self.stats.avg_response_time * self.stats.total_connections + response_time) /
                            (self.stats.total_connections + 1)
                        )
                        self.stats.total_connections += 1
                        return await response.json()
                        
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
                
        self.stats.failed_connections += 1
        self.stats.last_error = str(last_error)
        self.stats.last_error_time = datetime.now()
        raise last_error
        
    def _update_stats(self, success: bool, error: Optional[str] = None) -> None:
        """Ažurira statistiku konekcija."""
        if success:
            self.stats.total_connections += 1
        else:
            self.stats.failed_connections += 1
            self.stats.last_error = error
            self.stats.last_error_time = datetime.now()
            
    def get_stats(self) -> ConnectionStats:
        """Dohvaća statistiku konekcija."""
        return self.stats
        
    @contextmanager
    def socket_connection(self, host: str, port: int) -> socket.socket:
        """Kontekstni menadžer za socket konekciju."""
        sock = None
        try:
            sock = socket.create_connection((host, port), timeout=self.timeout)
            yield sock
        finally:
            if sock:
                sock.close()
                
    async def health_check(self, url: str) -> bool:
        """Provjerava zdravlje konekcije."""
        try:
            async with self.get_session(url) as session:
                async with session.get(url) as response:
                    return response.status == 200
        except Exception as e:
            self.logger.error(f"Greška pri health check-u: {e}")
            return False 