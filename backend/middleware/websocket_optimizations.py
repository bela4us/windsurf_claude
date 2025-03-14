from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import zlib
import time
from typing import Dict, List, Any
import logging
from functools import wraps
from django.core.cache import cache
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

class WebSocketOptimizer:
    def __init__(self):
        self.message_batch = []
        self.batch_size = 10
        self.batch_timeout = 0.1  # 100ms
        self.last_send_time = time.time()
        self.compression_threshold = 1024  # 1KB
        self.heartbeat_interval = 30  # 30 sekundi
        self.reconnect_attempts = 3
        self.reconnect_delay = 1  # 1 sekunda
        self.message_queue = {}
        self.connection_pool = {}
        self.max_connections = 1000

    def batch_messages(self, message: Dict[str, Any], group_name: str):
        """Batch poruke prije slanja"""
        self.message_batch.append(message)
        
        # Provjeri je li vrijeme za slanje batch-a
        current_time = time.time()
        if (len(self.message_batch) >= self.batch_size or 
            current_time - self.last_send_time >= self.batch_timeout):
            self._send_batch(group_name)

    def _send_batch(self, group_name: str):
        """Šalji batch poruke"""
        if not self.message_batch:
            return

        try:
            # Kompresiraj poruke ako su velike
            batch_data = self._compress_if_needed(self.message_batch)
            
            # Šalji batch
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'batch_message',
                    'data': batch_data
                }
            )
            
            self.message_batch = []
            self.last_send_time = time.time()
            
        except Exception as e:
            logger.error(f"Greška pri slanju batch-a: {e}")
            self._handle_error(e)

    def _compress_if_needed(self, data: List[Dict[str, Any]]) -> Any:
        """Kompresiraj podatke ako su veći od threshold-a"""
        json_data = json.dumps(data)
        if len(json_data) > self.compression_threshold:
            return {
                'compressed': True,
                'data': zlib.compress(json_data.encode())
            }
        return {
            'compressed': False,
            'data': data
        }

    def setup_heartbeat(self, consumer):
        """Postavi heartbeat mehanizam"""
        @wraps(consumer.receive)
        def wrapped_receive(self, *args, **kwargs):
            try:
                # Dodaj heartbeat u poruke
                if 'type' in kwargs and kwargs['type'] == 'heartbeat':
                    self._handle_heartbeat(consumer)
                return consumer.receive(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"Greška u heartbeat-u: {e}")
                return self._handle_error(e)
        return wrapped_receive

    def _handle_heartbeat(self, consumer):
        """Obrađuj heartbeat poruke"""
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.send)(
                consumer.channel_name,
                {
                    'type': 'heartbeat_response',
                    'timestamp': time.time()
                }
            )
        except Exception as e:
            logger.error(f"Greška pri obradi heartbeat-a: {e}")

    def setup_reconnection(self, consumer):
        """Postavi reconnection strategiju"""
        @wraps(consumer.disconnect)
        def wrapped_disconnect(self, *args, **kwargs):
            try:
                attempts = 0
                while attempts < self.reconnect_attempts:
                    try:
                        # Pokušaj ponovno povezivanje
                        time.sleep(self.reconnect_delay)
                        consumer.connect()
                        return
                    except Exception as e:
                        attempts += 1
                        logger.warning(f"Pokušaj {attempts} ponovnog povezivanja neuspješan: {e}")
                
                # Ako svi pokušaji neuspješni, prekini vezu
                return consumer.disconnect(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"Greška pri reconnection-u: {e}")
                return self._handle_error(e)
        return wrapped_disconnect

    def _handle_error(self, error: Exception):
        """Obrađuj greške"""
        logger.error(f"WebSocket greška: {error}")
        return None

    def manage_connection_pool(self, consumer):
        """Upravljanje pool-om konekcija"""
        if len(self.connection_pool) >= self.max_connections:
            # Ukloni najstariju konekciju
            oldest_conn = min(
                self.connection_pool.items(),
                key=lambda x: x[1]['created_at']
            )
            self.connection_pool.pop(oldest_conn[0])
            
        # Dodaj novu konekciju
        self.connection_pool[consumer.channel_name] = {
            'created_at': time.time(),
            'last_activity': time.time()
        }

    def update_connection_activity(self, consumer):
        """Ažuriraj aktivnost konekcije"""
        if consumer.channel_name in self.connection_pool:
            self.connection_pool[consumer.channel_name]['last_activity'] = time.time()

    def cleanup_inactive_connections(self):
        """Očisti neaktivne konekcije"""
        current_time = time.time()
        inactive_timeout = 300  # 5 minuta
        
        inactive_connections = [
            channel_name for channel_name, conn in self.connection_pool.items()
            if current_time - conn['last_activity'] > inactive_timeout
        ]
        
        for channel_name in inactive_connections:
            self.connection_pool.pop(channel_name)
            logger.info(f"Uklonjena neaktivna konekcija: {channel_name}")

    def queue_message(self, message: Dict[str, Any], group_name: str):
        """Postavi poruku u red"""
        if group_name not in self.message_queue:
            self.message_queue[group_name] = []
            
        self.message_queue[group_name].append({
            'message': message,
            'timestamp': time.time()
        })

    def process_message_queue(self):
        """Obradi poruke iz reda"""
        current_time = time.time()
        
        for group_name, queue in self.message_queue.items():
            if not queue:
                continue
                
            # Grupiraj poruke koje su starije od batch_timeout
            messages_to_send = [
                msg['message'] for msg in queue
                if current_time - msg['timestamp'] >= self.batch_timeout
            ]
            
            if messages_to_send:
                self._send_batch(group_name)
                
                # Ukloni obrađene poruke iz reda
                self.message_queue[group_name] = [
                    msg for msg in queue
                    if current_time - msg['timestamp'] < self.batch_timeout
                ]

# Inicijalizacija optimizatora
websocket_optimizer = WebSocketOptimizer() 