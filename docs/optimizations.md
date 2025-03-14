# Optimizacije Backend-a

## Pregled

Ovo je dokumentacija optimizacija implementiranih u backend dijelu aplikacije. Optimizacije su podijeljene u četiri glavne kategorije:

1. Database Layer optimizacije
2. Caching Layer optimizacije
3. WebSocket Layer optimizacije
4. API Layer optimizacije

## 1. Database Layer Optimizacije

### Bulk Operacije

```python
from utils.db_optimizations import db_optimizer

# Masovno stvaranje zapisa
games = db_optimizer.bulk_create(Game, [
    {'name': 'Game 1', 'status': 'active'},
    {'name': 'Game 2', 'status': 'active'}
])

# Masovno ažuriranje zapisa
db_optimizer.bulk_update(
    Game.objects.filter(status='active'),
    fields=['status']
)

# Masovno brisanje zapisa
db_optimizer.bulk_delete(Game.objects.filter(status='completed'))
```

### Optimizacija Upita

```python
# Optimizacija upita s select_related i prefetch_related
optimized_queryset = db_optimizer.optimize_query(Player.objects.all())

# Kreiranje indeksa
db_optimizer.create_indexes(Game, ['status', 'created_at'])
```

## 2. Caching Layer Optimizacije

### Redis Cache Manager

```python
from cache.redis_cache import cache_manager

# Postavljanje vrijednosti u cache
cache_manager.set('game:1', game_data)

# Dohvaćanje vrijednosti iz cache-a
game_data = cache_manager.get('game:1')

# Batch operacije
cache_manager.set_many({
    'game:1': game1_data,
    'game:2': game2_data
})

# Invalidacija cache-a
cache_manager.invalidate_pattern('game:*')
```

### Cache Dekorator

```python
@cache_manager.cache_key(timeout=300)
def get_game_stats(game_id):
    # Izračun statistike igre
    return stats
```

## 3. WebSocket Layer Optimizacije

### Rate Limiting i Message Batching

```python
from middleware.websocket_middleware import WebSocketOptimizer

optimizer = WebSocketOptimizer()

# Provjera rate limitinga
if not optimizer.should_rate_limit(consumer_id):
    # Procesiraj poruku
    pass

# Dodavanje poruke u batch
if optimizer.add_to_batch(consumer_id, message):
    # Šalji batch
    batch = optimizer.get_batch(consumer_id)
    await send_batch(batch)
```

### WebSocket Middleware

```python
# Konfiguracija u settings.py
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('127.0.0.1', 6379)],
        },
    },
}

MIDDLEWARE = [
    # ...
    'middleware.websocket_middleware.OptimizedWebSocketMiddleware',
]
```

## 4. API Layer Optimizacije

### Response Caching

```python
from utils.api_optimizations import api_optimizer

@api_optimizer.cache_response(timeout=300)
def game_list(request):
    # Dohvati listu igara
    return JsonResponse(games)
```

### Request Batching

```python
# Batch zahtjev
response = client.post(
    '/api/games/batch/',
    data=json.dumps([
        {'name': 'Game 1'},
        {'name': 'Game 2'}
    ]),
    HTTP_X_BATCH_REQUEST='true'
)
```

### Optimizirana Serializacija

```python
@api_optimizer.optimize_serialization(Game)
class GameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Game
        fields = '__all__'
```

## Performanse

### Očekivana Poboljšanja

1. **Database Layer**:
   - Bulk operacije: 5-10x brže od pojedinačnih operacija
   - Optimizirani upiti: 2-3x brže od neoptimiziranih
   - Indeksi: 10-100x brže pretraga

2. **Caching Layer**:
   - Cache hit: 100x brže od DB upita
   - Batch operacije: 3-5x brže od pojedinačnih
   - Distributed caching: Bolja skalabilnost

3. **WebSocket Layer**:
   - Rate limiting: Sprječava DoS napade
   - Message batching: 40-60% manje mrežnog prometa
   - Optimizirani broadcast: 30-50% manja latencija

4. **API Layer**:
   - Response caching: 10x brže odgovori
   - Request batching: 30-40% manje HTTP zahtjeva
   - Optimizirana serializacija: 20-30% brže odgovori

### Monitoring

Za praćenje performansi optimizacija, implementirane su sljedeće metrike:

1. **Database Metrike**:
   - Vrijeme izvršavanja upita
   - Broj DB round-trips
   - Učinkovitost bulk operacija

2. **Cache Metrike**:
   - Cache hit/miss ratio
   - Vrijeme pristupa cache-u
   - Učinkovitost invalidacije

3. **WebSocket Metrike**:
   - Broj poruka po sekundi
   - Veličina batch-a
   - Latencija poruka

4. **API Metrike**:
   - Vrijeme odgovora
   - Broj batch zahtjeva
   - Učinkovitost serializacije

## Konfiguracija

### Redis Postavke

```python
# settings.py
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
```

### Cache Timeout-i

```python
# settings.py
CACHE_TIMEOUT = {
    'GAME': 300,      # 5 minuta
    'PLAYER': 180,    # 3 minute
    'STATS': 600,     # 10 minuta
}
```

### Rate Limiting

```python
# settings.py
WEBSOCKET_RATE_LIMIT = 100  # poruka po sekundi
BATCH_SIZE = 10
BATCH_TIMEOUT = 0.1  # 100ms
```

## Troubleshooting

### Česti Problemi

1. **Cache Miss**:
   - Provjeri Redis konekciju
   - Provjeri cache key format
   - Provjeri cache timeout

2. **Rate Limiting**:
   - Povećaj limit ako je potrebno
   - Provjeri client-side throttling
   - Implementiraj retry logiku

3. **Batch Processing**:
   - Provjeri batch size
   - Provjeri timeout
   - Implementiraj error handling

### Debugging

```python
# Uključi detaljno logiranje
LOGGING = {
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'utils.db_optimizations': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'cache.redis_cache': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
``` 