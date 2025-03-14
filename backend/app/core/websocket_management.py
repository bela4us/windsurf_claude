from typing import Dict, Any, Optional, List, Callable, Union
import asyncio
import json
import threading
from datetime import datetime
from dataclasses import dataclass
import logging
from pathlib import Path
import websockets
from websockets.server import serve
from websockets.client import connect
import orjson
import time
from functools import wraps
import ssl
import signal
import sys
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

@dataclass
class WebSocketStats:
    total_connections: int = 0
    active_connections: int = 0
    total_messages: int = 0
    total_bytes: int = 0
    avg_message_size: float = 0.0
    last_cleanup: Optional[datetime] = None

class WebSocketManager:
    def __init__(
        self,
        ping_interval: float = 20.0,
        ping_timeout: float = 10.0,
        close_timeout: float = 5.0,
        max_message_size: int = 1024 * 1024,  # 1MB
        compression_threshold: int = 1024,  # 1KB
        cleanup_interval: float = 300.0  # 5 minuta
    ):
        self.logger = logging.getLogger(__name__)
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.close_timeout = close_timeout
        self.max_message_size = max_message_size
        self.compression_threshold = compression_threshold
        self.cleanup_interval = cleanup_interval
        
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_times: Dict[str, float] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.stats = WebSocketStats()
        
        self._start_cleanup_task()
        
    def _start_cleanup_task(self) -> None:
        """Započinje periodično čišćenje neaktivnih konekcija."""
        async def cleanup():
            while True:
                try:
                    await self._cleanup_inactive_connections()
                    await asyncio.sleep(self.cleanup_interval)
                except Exception as e:
                    self.logger.error(f"Greška pri čišćenju konekcija: {e}")
                    
        asyncio.create_task(cleanup())
        
    async def _cleanup_inactive_connections(self) -> None:
        """Čisti neaktivne konekcije."""
        current_time = time.time()
        inactive_connections = []
        
        for client_id, connection_time in self.connection_times.items():
            if current_time - connection_time > self.ping_timeout * 2:
                inactive_connections.append(client_id)
                
        for client_id in inactive_connections:
            await self.disconnect_client(client_id)
            
        self.stats.last_cleanup = datetime.now()
        
    async def connect_client(self, websocket: WebSocket, client_id: str) -> None:
        """Povezuje novog klijenta."""
        try:
            await websocket.accept()
            self.active_connections[client_id] = websocket
            self.connection_times[client_id] = time.time()
            
            self.stats.total_connections += 1
            self.stats.active_connections += 1
            
            self.logger.info(f"Klijent {client_id} povezan")
            
        except Exception as e:
            self.logger.error(f"Greška pri povezivanju klijenta {client_id}: {e}")
            raise
            
    async def disconnect_client(self, client_id: str) -> None:
        """Odvezuje klijenta."""
        try:
            if client_id in self.active_connections:
                websocket = self.active_connections[client_id]
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.close()
                    
                del self.active_connections[client_id]
                del self.connection_times[client_id]
                
                self.stats.active_connections -= 1
                
                self.logger.info(f"Klijent {client_id} odvezan")
                
        except Exception as e:
            self.logger.error(f"Greška pri odvezivanju klijenta {client_id}: {e}")
            
    async def process_message(
        self,
        websocket: WebSocket,
        client_id: str
    ) -> None:
        """Procesira poruke od klijenta."""
        try:
            while True:
                message = await websocket.receive_text()
                
                if len(message.encode()) > self.max_message_size:
                    await self.send_error(
                        websocket,
                        "Poruka prevelika",
                        code=1009
                    )
                    continue
                    
                self.connection_times[client_id] = time.time()
                
                try:
                    data = json.loads(message)
                    message_type = data.get("type")
                    
                    if message_type in self.message_handlers:
                        await self.message_handlers[message_type](data, client_id)
                    else:
                        await self.send_error(
                            websocket,
                            f"Nepoznati tip poruke: {message_type}",
                            code=1003
                        )
                        
                except json.JSONDecodeError:
                    await self.send_error(
                        websocket,
                        "Neispravan format JSON-a",
                        code=1007
                    )
                    
                self.stats.total_messages += 1
                self.stats.total_bytes += len(message.encode())
                self.stats.avg_message_size = (
                    self.stats.total_bytes / self.stats.total_messages
                )
                
        except WebSocketDisconnect:
            await self.disconnect_client(client_id)
        except Exception as e:
            self.logger.error(f"Greška pri procesiranju poruke: {e}")
            await self.disconnect_client(client_id)
            
    async def send_error(
        self,
        websocket: WebSocket,
        message: str,
        code: int = 1000
    ) -> None:
        """Šalje poruku o grešci klijentu."""
        try:
            await websocket.send_json({
                "type": "error",
                "code": code,
                "message": message
            })
        except Exception as e:
            self.logger.error(f"Greška pri slanju poruke o grešci: {e}")
            
    async def broadcast(
        self,
        message: Dict[str, Any],
        exclude: Optional[List[str]] = None
    ) -> None:
        """Šalje poruku svim klijentima."""
        try:
            exclude = exclude or []
            message_json = json.dumps(message)
            
            for client_id, websocket in self.active_connections.items():
                if client_id not in exclude:
                    try:
                        await websocket.send_text(message_json)
                    except Exception as e:
                        self.logger.error(
                            f"Greška pri slanju poruke klijentu {client_id}: {e}"
                        )
                        await self.disconnect_client(client_id)
                        
        except Exception as e:
            self.logger.error(f"Greška pri broadcastu poruke: {e}")
            
    def register_handler(
        self,
        message_type: str,
        handler: Callable
    ) -> None:
        """Registrira handler za tip poruke."""
        self.message_handlers[message_type] = handler
        
    def get_stats(self) -> WebSocketStats:
        """Dohvaća statistiku WebSocket konekcija."""
        return self.stats
        
    async def shutdown(self) -> None:
        """Zaustavlja upravljanje WebSocket konekcijama."""
        try:
            for client_id in list(self.active_connections.keys()):
                await self.disconnect_client(client_id)
        except Exception as e:
            self.logger.error(f"Greška pri zatvaranju WebSocket menadžera: {e}")

    async def start_server(self):
        """Započinje WebSocket server"""
        try:
            server = await serve(
                self._handle_connection,
                self.host,
                self.port,
                ssl=self.ssl_context,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
                max_size=self.max_message_size,
                compression=self.compression
            )
            
            logger.info(f"WebSocket server started on {self.host}:{self.port}")
            
            # Handle shutdown gracefully
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._shutdown(s)))
            
            await server.wait_closed()
        except Exception as e:
            logger.error(f"Error starting WebSocket server: {str(e)}")
            raise
    
    async def _handle_connection(self,
                               websocket: websockets.WebSocketServerProtocol,
                               path: str):
        """Upravlja novom WebSocket vezom"""
        client_id = id(websocket)
        
        try:
            with self._lock:
                self._connections[client_id] = websocket
                self._stats.total_connections += 1
                self._stats.active_connections += 1
            
            logger.info(f"New WebSocket connection: {client_id}")
            
            async for message in websocket:
                try:
                    # Ažuriraj vrijeme zadnje aktivnosti
                    websocket._last_activity = time.time()
                    
                    # Procesiraj poruku
                    await self._process_message(client_id, message)
                except websockets.exceptions.ConnectionClosed:
                    break
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    await self._send_error(client_id, str(e))
        finally:
            await self._close_connection(client_id)
    
    async def _process_message(self,
                             client_id: str,
                             message: Union[str, bytes]):
        """Procesira WebSocket poruku"""
        try:
            # Deserijaliziraj poruku
            if isinstance(message, bytes):
                data = orjson.loads(message)
            else:
                data = json.loads(message)
            
            # Pronađi i izvrši handler
            handler = self._handlers.get(data.get('type'))
            if handler:
                await handler(client_id, data)
            else:
                await self._send_error(client_id, f"Unknown message type: {data.get('type')}")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            await self._send_error(client_id, str(e))
    
    async def _send_error(self, client_id: str, error: str):
        """Šalje poruku o grešci klijentu"""
        try:
            message = {
                'type': 'error',
                'error': error
            }
            await self.send_message(client_id, message)
        except Exception as e:
            logger.error(f"Error sending error message: {str(e)}")
    
    async def send_message(self,
                          client_id: str,
                          message: Dict[str, Any]) -> bool:
        """Šalje poruku klijentu"""
        try:
            with self._lock:
                if client_id not in self._connections:
                    return False
                
                connection = self._connections[client_id]
                if connection.closed:
                    return False
            
            # Serijaliziraj poruku
            serialized = orjson.dumps(message)
            
            # Pošalji poruku
            await connection.send(serialized)
            
            # Ažuriraj statistiku
            with self._lock:
                self._stats.messages_sent += 1
                self._stats.bytes_sent += len(serialized)
            
            return True
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return False
    
    async def broadcast(self,
                       message: Dict[str, Any],
                       exclude: Optional[List[str]] = None) -> int:
        """Šalje poruku svim klijentima"""
        try:
            exclude = exclude or []
            sent_count = 0
            
            with self._lock:
                client_ids = [
                    client_id for client_id in self._connections.keys()
                    if client_id not in exclude
                ]
            
            for client_id in client_ids:
                if await self.send_message(client_id, message):
                    sent_count += 1
            
            return sent_count
        except Exception as e:
            logger.error(f"Error broadcasting message: {str(e)}")
            return 0
    
    async def _close_connection(self, client_id: str):
        """Zatvara WebSocket vezu"""
        try:
            with self._lock:
                if client_id in self._connections:
                    connection = self._connections[client_id]
                    if not connection.closed:
                        await connection.close()
                    del self._connections[client_id]
                    self._stats.active_connections -= 1
        except Exception as e:
            logger.error(f"Error closing connection: {str(e)}")
    
    def register_handler(self, message_type: str, handler: Callable):
        """Registrira handler za određenu vrstu poruke"""
        self._handlers[message_type] = handler
    
    async def connect_client(self,
                           url: str,
                           on_message: Optional[Callable] = None,
                           on_error: Optional[Callable] = None,
                           on_close: Optional[Callable] = None) -> str:
        """Povezuje se s WebSocket serverom kao klijent"""
        try:
            websocket = await connect(
                url,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
                max_size=self.max_message_size,
                compression=self.compression
            )
            
            client_id = id(websocket)
            
            with self._lock:
                self._connections[client_id] = websocket
                self._stats.total_connections += 1
                self._stats.active_connections += 1
            
            # Pokreni task za čitanje poruka
            asyncio.create_task(
                self._handle_client_messages(
                    client_id,
                    websocket,
                    on_message,
                    on_error,
                    on_close
                )
            )
            
            return client_id
        except Exception as e:
            logger.error(f"Error connecting to WebSocket server: {str(e)}")
            raise
    
    async def _handle_client_messages(self,
                                    client_id: str,
                                    websocket: websockets.WebSocketClientProtocol,
                                    on_message: Optional[Callable],
                                    on_error: Optional[Callable],
                                    on_close: Optional[Callable]):
        """Upravlja porukama klijentske veze"""
        try:
            async for message in websocket:
                try:
                    # Ažuriraj vrijeme zadnje aktivnosti
                    websocket._last_activity = time.time()
                    
                    # Procesiraj poruku
                    if on_message:
                        await on_message(message)
                except websockets.exceptions.ConnectionClosed:
                    break
                except Exception as e:
                    logger.error(f"Error processing client message: {str(e)}")
                    if on_error:
                        await on_error(e)
        finally:
            await self._close_connection(client_id)
            if on_close:
                await on_close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Dohvaća statistiku WebSocket veza"""
        try:
            with self._lock:
                return {
                    'total_connections': self._stats.total_connections,
                    'active_connections': self._stats.active_connections,
                    'messages_sent': self._stats.messages_sent,
                    'messages_received': self._stats.messages_received,
                    'bytes_sent': self._stats.bytes_sent,
                    'bytes_received': self._stats.bytes_received,
                    'avg_latency': self._stats.avg_latency,
                    'last_cleanup': self._stats.last_cleanup.isoformat()
                }
        except Exception as e:
            logger.error(f"Error getting WebSocket stats: {str(e)}")
            return {}
    
    async def _shutdown(self, sig: signal.Signals):
        """Zatvara WebSocket server"""
        logger.info(f"Received exit signal {sig.name}...")
        
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("WebSocket server stopped")
        sys.exit(0)
    
    def shutdown(self):
        """Zatvara WebSocket manager"""
        asyncio.create_task(self._shutdown(signal.SIGTERM)) 