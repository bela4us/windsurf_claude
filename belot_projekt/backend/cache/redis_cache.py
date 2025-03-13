"""
Konfiguracija i integracija Redis cache sustava za Belot aplikaciju.

Ovaj modul omogućuje korištenje Redis-a kao sustava za cachiranje
podataka u aplikaciji, poboljšavajući performanse kroz smanjivanje
potrebe za opetovanim dohvaćanjem istih podataka iz baze podataka.
"""

import json
import logging
import pickle
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import timedelta

import redis
from django.conf import settings
from django.core.cache import cache
from django.core.cache.backends.redis import RedisCache as DjangoRedisCache

logger = logging.getLogger('belot.cache')


def get_redis_connection() -> redis.Redis:
    """
    Dohvaća Redis konekciju iz Django cache postavki.
    
    Returns:
        redis.Redis: Redis konekcija
        
    Raises:
        ValueError: Ako Django nije konfiguriran za korištenje Redis cachea
    """
    try:
        if not isinstance(cache, DjangoRedisCache):
            # Umjesto bacanja greške, pokušavamo direktno povezivanje
            import redis
            logger.warning("Django nije konfiguriran za Redis cache, pokušavam direktno povezivanje")
            return redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=0
            )
        
        # Dohvatimo raw Redis konekciju iz Django cache objekta
        return cache._cache.get_client()
    except Exception as e:
        logger.error(f"Greška pri povezivanju s Redis-om: {e}")
        # Vraćamo None umjesto bacanja iznimke
        return None


class RedisCache:
    """
    Wrapper klasa koja pruža dodatne funkcionalnosti iznad Django cache API-ja.
    
    Ova klasa omogućuje napredno upravljanje Redis cachingom, uključujući
    podršku za kompleksnije strukture podataka, pattern-based invalidaciju,
    i automatsko serijaliziranje/deserijaliziranje podataka.
    """
    
    def __init__(self, prefix: str = "belot", use_pickle: bool = False):
        """
        Inicijalizira RedisCache instancu.
        
        Args:
            prefix: Prefiks koji se dodaje svim ključevima
            use_pickle: Koristi pickle za serijalizaciju umjesto JSON-a
        """
        self.prefix = prefix
        self.use_pickle = use_pickle
        self.redis_conn = get_redis_connection()
    
    def _prefixed_key(self, key: str) -> str:
        """
        Dodaje prefiks ključu.
        
        Args:
            key: Originalni ključ
            
        Returns:
            str: Ključ s prefiksom
        """
        return f"{self.prefix}:{key}"
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Dohvaća vrijednost iz cachea.
        
        Args:
            key: Ključ za dohvat
            default: Zadana vrijednost ako ključ ne postoji
            
        Returns:
            Any: Vrijednost iz cachea ili default
        """
        prefixed_key = self._prefixed_key(key)
        cached_value = self.redis_conn.get(prefixed_key)
        
        if cached_value is None:
            return default
        
        try:
            if self.use_pickle:
                return pickle.loads(cached_value)
            else:
                return json.loads(cached_value)
        except (pickle.PickleError, json.JSONDecodeError) as e:
            logger.error(f"Greška pri deserijalizaciji vrijednosti za ključ {key}: {e}")
            return default
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """
        Postavlja vrijednost u cache.
        
        Args:
            key: Ključ za postavljanje
            value: Vrijednost za spremanje
            timeout: Vrijeme isteka u sekundama
            
        Returns:
            bool: True ako je uspješno postavljeno
        """
        prefixed_key = self._prefixed_key(key)
        
        try:
            if self.use_pickle:
                serialized = pickle.dumps(value)
            else:
                serialized = json.dumps(value)
            
            if timeout is not None:
                return bool(self.redis_conn.setex(prefixed_key, timeout, serialized))
            else:
                return bool(self.redis_conn.set(prefixed_key, serialized))
        except (pickle.PickleError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Greška pri serijalizaciji vrijednosti za ključ {key}: {e}")
            return False
    
    def delete(self, key: str) -> int:
        """
        Briše ključ iz cachea.
        
        Args:
            key: Ključ za brisanje
            
        Returns:
            int: Broj obrisanih ključeva
        """
        prefixed_key = self._prefixed_key(key)
        return self.redis_conn.delete(prefixed_key)
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Briše sve ključeve koji odgovaraju uzorku.
        
        Args:
            pattern: Uzorak za brisanje (npr. "user:*")
            
        Returns:
            int: Broj obrisanih ključeva
        """
        prefixed_pattern = self._prefixed_key(pattern)
        keys = self.redis_conn.keys(prefixed_pattern)
        
        if not keys:
            return 0
        
        return self.redis_conn.delete(*keys)
    
    def exists(self, key: str) -> bool:
        """
        Provjerava postoji li ključ u cacheu.
        
        Args:
            key: Ključ za provjeru
            
        Returns:
            bool: True ako ključ postoji
        """
        prefixed_key = self._prefixed_key(key)
        return bool(self.redis_conn.exists(prefixed_key))
    
    def clear(self) -> bool:
        """
        Briše sve ključeve s prefiksom.
        
        Returns:
            bool: True ako je uspješno obrisano
        """
        pattern = self._prefixed_key("*")
        keys = self.redis_conn.keys(pattern)
        
        if not keys:
            return True
        
        return bool(self.redis_conn.delete(*keys))
    
    def incr(self, key: str, amount: int = 1) -> int:
        """
        Inkrementira vrijednost za ključ.
        
        Args:
            key: Ključ za inkrementiranje
            amount: Iznos za inkrementiranje
            
        Returns:
            int: Nova vrijednost
        """
        prefixed_key = self._prefixed_key(key)
        return self.redis_conn.incrby(prefixed_key, amount)
    
    def decr(self, key: str, amount: int = 1) -> int:
        """
        Dekrementira vrijednost za ključ.
        
        Args:
            key: Ključ za dekrementiranje
            amount: Iznos za dekrementiranje
            
        Returns:
            int: Nova vrijednost
        """
        prefixed_key = self._prefixed_key(key)
        return self.redis_conn.decrby(prefixed_key, amount)
    
    def ttl(self, key: str) -> int:
        """
        Dohvaća vrijeme do isteka za ključ.
        
        Args:
            key: Ključ za dohvat TTL-a
            
        Returns:
            int: Vrijeme do isteka u sekundama, -1 ako nema isteka, -2 ako ključ ne postoji
        """
        prefixed_key = self._prefixed_key(key)
        return self.redis_conn.ttl(prefixed_key)
    
    def expire(self, key: str, timeout: int) -> bool:
        """
        Postavlja vrijeme isteka za ključ.
        
        Args:
            key: Ključ za postavljanje isteka
            timeout: Vrijeme isteka u sekundama
            
        Returns:
            bool: True ako je uspješno postavljeno
        """
        prefixed_key = self._prefixed_key(key)
        return bool(self.redis_conn.expire(prefixed_key, timeout))
    
    def hset(self, name: str, key: str, value: Any) -> int:
        """
        Postavlja vrijednost u hash.
        
        Args:
            name: Ime hasha
            key: Ključ u hashu
            value: Vrijednost za spremanje
            
        Returns:
            int: 1 ako je dodano novo polje, 0 ako je ažurirano postojeće
        """
        prefixed_name = self._prefixed_key(name)
        
        try:
            if self.use_pickle:
                serialized = pickle.dumps(value)
            else:
                serialized = json.dumps(value)
            
            return self.redis_conn.hset(prefixed_name, key, serialized)
        except (pickle.PickleError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Greška pri serijalizaciji hash vrijednosti {name}:{key}: {e}")
            return 0
    
    def hget(self, name: str, key: str, default: Any = None) -> Any:
        """
        Dohvaća vrijednost iz hasha.
        
        Args:
            name: Ime hasha
            key: Ključ u hashu
            default: Zadana vrijednost ako ključ ne postoji
            
        Returns:
            Any: Vrijednost iz hasha ili default
        """
        prefixed_name = self._prefixed_key(name)
        value = self.redis_conn.hget(prefixed_name, key)
        
        if value is None:
            return default
        
        try:
            if self.use_pickle:
                return pickle.loads(value)
            else:
                return json.loads(value)
        except (pickle.PickleError, json.JSONDecodeError) as e:
            logger.error(f"Greška pri deserijalizaciji hash vrijednosti {name}:{key}: {e}")
            return default
    
    def hgetall(self, name: str) -> Dict[str, Any]:
        """
        Dohvaća sve vrijednosti iz hasha.
        
        Args:
            name: Ime hasha
            
        Returns:
            Dict[str, Any]: Sve vrijednosti iz hasha
        """
        prefixed_name = self._prefixed_key(name)
        raw_values = self.redis_conn.hgetall(prefixed_name)
        
        result = {}
        for key, value in raw_values.items():
            key_str = key.decode() if isinstance(key, bytes) else key
            
            try:
                if self.use_pickle:
                    result[key_str] = pickle.loads(value)
                else:
                    result[key_str] = json.loads(value)
            except (pickle.PickleError, json.JSONDecodeError) as e:
                logger.error(f"Greška pri deserijalizaciji hash vrijednosti {name}:{key_str}: {e}")
                result[key_str] = None
        
        return result
    
    def hdel(self, name: str, *keys: str) -> int:
        """
        Briše ključeve iz hasha.
        
        Args:
            name: Ime hasha
            *keys: Ključevi za brisanje
            
        Returns:
            int: Broj obrisanih ključeva
        """
        prefixed_name = self._prefixed_key(name)
        return self.redis_conn.hdel(prefixed_name, *keys)
    
    def pipeline(self) -> 'RedisCachePipeline':
        """
        Stvara pipeline za batching operacija.
        
        Returns:
            RedisCachePipeline: Pipeline objekt
        """
        return RedisCachePipeline(self)


class RedisCachePipeline:
    """
    Pipeline klasa za batching Redis operacija.
    
    Ova klasa omogućuje izvršavanje više Redis operacija kao jednu
    atomsku transakciju, poboljšavajući performanse i konzistentnost.
    """
    
    def __init__(self, cache: RedisCache):
        """
        Inicijalizira pipeline.
        
        Args:
            cache: RedisCache instanca
        """
        self.cache = cache
        self.pipeline = self.cache.redis_conn.pipeline()
    
    def get(self, key: str) -> 'RedisCachePipeline':
        """
        Dodaje get operaciju u pipeline.
        
        Args:
            key: Ključ za dohvat
            
        Returns:
            RedisCachePipeline: self za chaining
        """
        prefixed_key = self.cache._prefixed_key(key)
        self.pipeline.get(prefixed_key)
        return self
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> 'RedisCachePipeline':
        """
        Dodaje set operaciju u pipeline.
        
        Args:
            key: Ključ za postavljanje
            value: Vrijednost za spremanje
            timeout: Vrijeme isteka u sekundama
            
        Returns:
            RedisCachePipeline: self za chaining
        """
        prefixed_key = self.cache._prefixed_key(key)
        
        try:
            if self.cache.use_pickle:
                serialized = pickle.dumps(value)
            else:
                serialized = json.dumps(value)
            
            if timeout is not None:
                self.pipeline.setex(prefixed_key, timeout, serialized)
            else:
                self.pipeline.set(prefixed_key, serialized)
            
            return self
        except (pickle.PickleError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Greška pri serijalizaciji vrijednosti za ključ {key}: {e}")
            return self
    
    def delete(self, key: str) -> 'RedisCachePipeline':
        """
        Dodaje delete operaciju u pipeline.
        
        Args:
            key: Ključ za brisanje
            
        Returns:
            RedisCachePipeline: self za chaining
        """
        prefixed_key = self.cache._prefixed_key(key)
        self.pipeline.delete(prefixed_key)
        return self
    
    def exists(self, key: str) -> 'RedisCachePipeline':
        """
        Dodaje exists operaciju u pipeline.
        
        Args:
            key: Ključ za provjeru
            
        Returns:
            RedisCachePipeline: self za chaining
        """
        prefixed_key = self.cache._prefixed_key(key)
        self.pipeline.exists(prefixed_key)
        return self
    
    def incr(self, key: str, amount: int = 1) -> 'RedisCachePipeline':
        """
        Dodaje incr operaciju u pipeline.
        
        Args:
            key: Ključ za inkrementiranje
            amount: Iznos za inkrementiranje
            
        Returns:
            RedisCachePipeline: self za chaining
        """
        prefixed_key = self.cache._prefixed_key(key)
        self.pipeline.incrby(prefixed_key, amount)
        return self
    
    def hset(self, name: str, key: str, value: Any) -> 'RedisCachePipeline':
        """
        Dodaje hset operaciju u pipeline.
        
        Args:
            name: Ime hasha
            key: Ključ u hashu
            value: Vrijednost za spremanje
            
        Returns:
            RedisCachePipeline: self za chaining
        """
        prefixed_name = self.cache._prefixed_key(name)
        
        try:
            if self.cache.use_pickle:
                serialized = pickle.dumps(value)
            else:
                serialized = json.dumps(value)
            
            self.pipeline.hset(prefixed_name, key, serialized)
            return self
        except (pickle.PickleError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Greška pri serijalizaciji hash vrijednosti {name}:{key}: {e}")
            return self
    
    def hget(self, name: str, key: str) -> 'RedisCachePipeline':
        """
        Dodaje hget operaciju u pipeline.
        
        Args:
            name: Ime hasha
            key: Ključ u hashu
            
        Returns:
            RedisCachePipeline: self za chaining
        """
        prefixed_name = self.cache._prefixed_key(name)
        self.pipeline.hget(prefixed_name, key)
        return self
    
    def hdel(self, name: str, *keys: str) -> 'RedisCachePipeline':
        """
        Dodaje hdel operaciju u pipeline.
        
        Args:
            name: Ime hasha
            *keys: Ključevi za brisanje
            
        Returns:
            RedisCachePipeline: self za chaining
        """
        prefixed_name = self.cache._prefixed_key(name)
        self.pipeline.hdel(prefixed_name, *keys)
        return self
    
    def execute(self) -> List[Any]:
        """
        Izvršava sve operacije u pipelineu.
        
        Returns:
            List[Any]: Rezultati izvršenih operacija
        """
        results = self.pipeline.execute()
        processed_results = []
        
        for i, result in enumerate(results):
            # Deserijaliziraj rezultate za get i hget operacije
            command = self.pipeline.command_stack[i][0]
            
            if command == b'GET' and result is not None:
                try:
                    if self.cache.use_pickle:
                        processed_results.append(pickle.loads(result))
                    else:
                        processed_results.append(json.loads(result))
                except (pickle.PickleError, json.JSONDecodeError) as e:
                    logger.error(f"Greška pri deserijalizaciji GET rezultata: {e}")
                    processed_results.append(None)
            
            elif command == b'HGET' and result is not None:
                try:
                    if self.cache.use_pickle:
                        processed_results.append(pickle.loads(result))
                    else:
                        processed_results.append(json.loads(result))
                except (pickle.PickleError, json.JSONDecodeError) as e:
                    logger.error(f"Greška pri deserijalizaciji HGET rezultata: {e}")
                    processed_results.append(None)
            
            else:
                processed_results.append(result)
        
        return processed_results


# Primjer funkcija za rad s često korištenim tipovima podataka

def cache_game_data(game_id: str, data: Dict[str, Any], timeout: int = 3600) -> bool:
    """
    Sprema podatke o igri u cache.
    
    Args:
        game_id: ID igre
        data: Podaci o igri
        timeout: Vrijeme isteka u sekundama
        
    Returns:
        bool: True ako je uspješno spremljeno
    """
    cache = RedisCache(prefix="game")
    return cache.set(game_id, data, timeout)


def get_cached_game_data(game_id: str) -> Optional[Dict[str, Any]]:
    """
    Dohvaća podatke o igri iz cachea.
    
    Args:
        game_id: ID igre
        
    Returns:
        Optional[Dict[str, Any]]: Podaci o igri ili None
    """
    cache = RedisCache(prefix="game")
    return cache.get(game_id)


def invalidate_game_cache(game_id: str) -> int:
    """
    Invalidira cache za igru.
    
    Args:
        game_id: ID igre
        
    Returns:
        int: Broj invalidiranih ključeva
    """
    cache = RedisCache(prefix="game")
    return cache.delete(game_id)


def cache_user_data(user_id: str, data: Dict[str, Any], timeout: int = 3600) -> bool:
    """
    Sprema podatke o korisniku u cache.
    
    Args:
        user_id: ID korisnika
        data: Podaci o korisniku
        timeout: Vrijeme isteka u sekundama
        
    Returns:
        bool: True ako je uspješno spremljeno
    """
    cache = RedisCache(prefix="user")
    return cache.set(user_id, data, timeout)


def get_cached_user_data(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Dohvaća podatke o korisniku iz cachea.
    
    Args:
        user_id: ID korisnika
        
    Returns:
        Optional[Dict[str, Any]]: Podaci o korisniku ili None
    """
    cache = RedisCache(prefix="user")
    return cache.get(user_id)


def invalidate_user_cache(user_id: str) -> int:
    """
    Invalidira cache za korisnika.
    
    Args:
        user_id: ID korisnika
        
    Returns:
        int: Broj invalidiranih ključeva
    """
    cache = RedisCache(prefix="user")
    return cache.delete(user_id)


def cache_room_data(room_id: str, data: Dict[str, Any], timeout: int = 1800) -> bool:
    """
    Sprema podatke o sobi u cache.
    
    Args:
        room_id: ID sobe
        data: Podaci o sobi
        timeout: Vrijeme isteka u sekundama
        
    Returns:
        bool: True ako je uspješno spremljeno
    """
    cache = RedisCache(prefix="room")
    return cache.set(room_id, data, timeout)


def get_cached_room_data(room_id: str) -> Optional[Dict[str, Any]]:
    """
    Dohvaća podatke o sobi iz cachea.
    
    Args:
        room_id: ID sobe
        
    Returns:
        Optional[Dict[str, Any]]: Podaci o sobi ili None
    """
    cache = RedisCache(prefix="room")
    return cache.get(room_id)


def invalidate_room_cache(room_id: str) -> int:
    """
    Invalidira cache za sobu.
    
    Args:
        room_id: ID sobe
        
    Returns:
        int: Broj invalidiranih ključeva
    """
    cache = RedisCache(prefix="room")
    return cache.delete(room_id)