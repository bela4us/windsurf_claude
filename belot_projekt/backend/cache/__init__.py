"""
Inicijalizacijski modul za cache komponentu Belot aplikacije.

Ovaj modul omogućuje centralizirano upravljanje cache postavkama
i funkcionalnostima koje koriste različiti dijelovi aplikacije.
Pruža integraciju s Redis cache sustavom i optimizaciju performansi
kroz napredne strategije cachiranja.
"""

from .redis_cache import RedisCache, get_redis_connection

__all__ = [
    'RedisCache',
    'get_redis_connection',
]