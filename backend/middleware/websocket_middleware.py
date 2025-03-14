<<<<<<< HEAD
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.core.cache import cache
import json
import time
import logging
from typing import Dict, List, Any
from collections import defaultdict

logger = logging.getLogger(__name__)

class WebSocketOptimizer:
    def __init__(self):
        self.message_batch_size = 10
        self.batch_timeout = 0.1  # 100ms
        self.rate_limit = 100  # poruka po sekundi
        self._message_batches: Dict[str, List[Dict]] = defaultdict(list)
        self._last_send_time: Dict[str, float] = defaultdict(float)
        self._message_count: Dict[str, int] = defaultdict(int)
        self._last_reset_time: Dict[str, float] = defaultdict(float)

    def should_rate_limit(self, consumer_id: str) -> bool:
        """Provjerava rate limiting"""
        current_time = time.time()
        
        # Resetiraj brojač ako je prošla sekunda
        if current_time - self._last_reset_time[consumer_id] >= 1.0:
            self._message_count[consumer_id] = 0
            self._last_reset_time[consumer_id] = current_time
        
        # Provjeri limit
        if self._message_count[consumer_id] >= self.rate_limit:
            return True
        
        self._message_count[consumer_id] += 1
        return False

    def add_to_batch(self, consumer_id: str, message: Dict) -> bool:
        """Dodaje poruku u batch"""
        self._message_batches[consumer_id].append(message)
        
        # Ako je batch pun ili je prošlo dovoljno vremena, šalji
        if (len(self._message_batches[consumer_id]) >= self.message_batch_size or
            time.time() - self._last_send_time[consumer_id] >= self.batch_timeout):
            return True
        return False

    def get_batch(self, consumer_id: str) -> List[Dict]:
        """Dohvaća batch poruka"""
        batch = self._message_batches[consumer_id]
        self._message_batches[consumer_id] = []
        self._last_send_time[consumer_id] = time.time()
        return batch

    def clear_batch(self, consumer_id: str) -> None:
        """Briše batch poruka"""
        self._message_batches[consumer_id] = []
        self._last_send_time[consumer_id] = 0

class OptimizedWebSocketMiddleware(BaseMiddleware):
    def __init__(self, inner):
        super().__init__(inner)
        self.optimizer = WebSocketOptimizer()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "websocket":
            return await super().__call__(scope, receive, send)

        consumer_id = f"{scope['client'][0]}:{scope['client'][1]}"

        async def optimized_receive():
            message = await receive()
            if message["type"] == "websocket.receive":
                # Rate limiting
                if self.optimizer.should_rate_limit(consumer_id):
                    logger.warning(f"Rate limit prekoračen za {consumer_id}")
                    return None
            return message

        async def optimized_send(message):
            if message["type"] == "websocket.send":
                # Dodaj u batch
                if self.optimizer.add_to_batch(consumer_id, message):
                    # Šalji batch
                    batch = self.optimizer.get_batch(consumer_id)
                    if batch:
                        await send({
                            "type": "websocket.send",
                            "text": json.dumps(batch)
                        })
            else:
                await send(message)

        try:
            return await super().__call__(scope, optimized_receive, optimized_send)
        finally:
            # Očisti batch pri zatvaranju
            self.optimizer.clear_batch(consumer_id)

class WebSocketAuthenticationMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        if scope["type"] != "websocket":
            return await super().__call__(scope, receive, send)

        # Dohvati token iz query stringa
        query_string = scope.get("query_string", b"").decode()
        token = dict(param.split("=") for param in query_string.split("&"))["token"]

        # Provjeri token
        if not await self.validate_token(token):
            await send({
                "type": "websocket.close",
                "code": 4001,
                "reason": "Invalid token"
            })
            return

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def validate_token(self, token):
        # Implementiraj validaciju tokena
=======
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.core.cache import cache
import json
import time
import logging
from typing import Dict, List, Any
from collections import defaultdict

logger = logging.getLogger(__name__)

class WebSocketOptimizer:
    def __init__(self):
        self.message_batch_size = 10
        self.batch_timeout = 0.1  # 100ms
        self.rate_limit = 100  # poruka po sekundi
        self._message_batches: Dict[str, List[Dict]] = defaultdict(list)
        self._last_send_time: Dict[str, float] = defaultdict(float)
        self._message_count: Dict[str, int] = defaultdict(int)
        self._last_reset_time: Dict[str, float] = defaultdict(float)

    def should_rate_limit(self, consumer_id: str) -> bool:
        """Provjerava rate limiting"""
        current_time = time.time()
        
        # Resetiraj brojač ako je prošla sekunda
        if current_time - self._last_reset_time[consumer_id] >= 1.0:
            self._message_count[consumer_id] = 0
            self._last_reset_time[consumer_id] = current_time
        
        # Provjeri limit
        if self._message_count[consumer_id] >= self.rate_limit:
            return True
        
        self._message_count[consumer_id] += 1
        return False

    def add_to_batch(self, consumer_id: str, message: Dict) -> bool:
        """Dodaje poruku u batch"""
        self._message_batches[consumer_id].append(message)
        
        # Ako je batch pun ili je prošlo dovoljno vremena, šalji
        if (len(self._message_batches[consumer_id]) >= self.message_batch_size or
            time.time() - self._last_send_time[consumer_id] >= self.batch_timeout):
            return True
        return False

    def get_batch(self, consumer_id: str) -> List[Dict]:
        """Dohvaća batch poruka"""
        batch = self._message_batches[consumer_id]
        self._message_batches[consumer_id] = []
        self._last_send_time[consumer_id] = time.time()
        return batch

    def clear_batch(self, consumer_id: str) -> None:
        """Briše batch poruka"""
        self._message_batches[consumer_id] = []
        self._last_send_time[consumer_id] = 0

class OptimizedWebSocketMiddleware(BaseMiddleware):
    def __init__(self, inner):
        super().__init__(inner)
        self.optimizer = WebSocketOptimizer()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "websocket":
            return await super().__call__(scope, receive, send)

        consumer_id = f"{scope['client'][0]}:{scope['client'][1]}"

        async def optimized_receive():
            message = await receive()
            if message["type"] == "websocket.receive":
                # Rate limiting
                if self.optimizer.should_rate_limit(consumer_id):
                    logger.warning(f"Rate limit prekoračen za {consumer_id}")
                    return None
            return message

        async def optimized_send(message):
            if message["type"] == "websocket.send":
                # Dodaj u batch
                if self.optimizer.add_to_batch(consumer_id, message):
                    # Šalji batch
                    batch = self.optimizer.get_batch(consumer_id)
                    if batch:
                        await send({
                            "type": "websocket.send",
                            "text": json.dumps(batch)
                        })
            else:
                await send(message)

        try:
            return await super().__call__(scope, optimized_receive, optimized_send)
        finally:
            # Očisti batch pri zatvaranju
            self.optimizer.clear_batch(consumer_id)

class WebSocketAuthenticationMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        if scope["type"] != "websocket":
            return await super().__call__(scope, receive, send)

        # Dohvati token iz query stringa
        query_string = scope.get("query_string", b"").decode()
        token = dict(param.split("=") for param in query_string.split("&"))["token"]

        # Provjeri token
        if not await self.validate_token(token):
            await send({
                "type": "websocket.close",
                "code": 4001,
                "reason": "Invalid token"
            })
            return

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def validate_token(self, token):
        # Implementiraj validaciju tokena
>>>>>>> c45eb88e3e23e6f6a3bf252c5a572f1c5cdb8266
        return True  # Placeholder 