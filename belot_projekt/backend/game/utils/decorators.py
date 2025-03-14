"""
Dekoratori za mjerenje performansi i praćenje izvršavanja u igri Belota.

Ovaj modul sadrži dekoratore koji se koriste za mjerenje performansi,
keširanje rezultata i praćenje izvršavanja različitih metoda u igri,
pružajući alate za optimizaciju i dijagnostiku.
"""

import time
import logging
import functools
from typing import Any, Callable, Dict, Optional, List, Union

# Postavljanje loggera za praćenje aktivnosti
logger = logging.getLogger(__name__)

def track_execution_time(func):
    """
    Dekorator koji mjeri i bilježi vrijeme izvršavanja funkcije ili metode.
    
    Args:
        func: Funkcija ili metoda koja se dekorira
    
    Returns:
        Dekorirana funkcija ili metoda
    
    Primjer:
        @track_execution_time
        def moja_funkcija():
            # kod funkcije
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Bilježenje početnog vremena
        start_time = time.time()
        
        # Izvršavanje funkcije
        result = func(*args, **kwargs)
        
        # Računanje trajanja
        duration = time.time() - start_time
        
        # Dohvaćanje imena klase, ako je metoda
        if args and hasattr(args[0], '__class__'):
            class_name = args[0].__class__.__name__
            func_name = f"{class_name}.{func.__name__}"
        else:
            func_name = func.__name__
            
        # Logiranje vremena izvršavanja
        logger.info(f"PERF: {func_name} izvršeno za {duration:.6f} sekundi")
        
        return result
    
    return wrapper

def log_calls(func):
    """
    Dekorator koji bilježi pozive funkcije ili metode s argumentima.
    
    Args:
        func: Funkcija ili metoda koja se dekorira
        
    Returns:
        Dekorirana funkcija ili metoda
        
    Primjer:
        @log_calls
        def moja_funkcija(arg1, arg2):
            # kod funkcije
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Dohvaćanje imena klase, ako je metoda
        if args and hasattr(args[0], '__class__'):
            class_name = args[0].__class__.__name__
            func_name = f"{class_name}.{func.__name__}"
            # Preskakanje self argumenta
            call_args = args[1:] 
        else:
            func_name = func.__name__
            call_args = args
            
        # Logiranje poziva
        args_str = ", ".join([str(arg) for arg in call_args])
        kwargs_str = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        params = ", ".join(filter(None, [args_str, kwargs_str]))
        
        logger.debug(f"CALL: {func_name}({params})")
        
        # Izvršavanje funkcije
        result = func(*args, **kwargs)
        
        return result
        
    return wrapper

def memoize(func):
    """
    Dekorator koji kešira rezultate funkcije ili metode.
    
    Slično kao lru_cache, ali s boljom podrškom za objekte.
    
    Args:
        func: Funkcija ili metoda koja se dekorira
        
    Returns:
        Dekorirana funkcija ili metoda
        
    Primjer:
        @memoize
        def dugotrajna_funkcija(arg1, arg2):
            # kod funkcije
    """
    cache = {}
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Generiranje ključa za keš
        # Za metode, prvi argument (self) se preskače
        if args and hasattr(args[0], '__class__'):
            # Metoda: koristimo id objekta umjesto samog objekta
            key_args = (id(args[0]),) + args[1:]
        else:
            # Funkcija: koristimo sve argumente
            key_args = args
            
        # Dodavanje kwargs u ključ
        key_kwargs = frozenset(kwargs.items())
        
        # Konačni ključ
        key = (key_args, key_kwargs)
        
        # Provjera je li rezultat već u kešu
        if key in cache:
            return cache[key]
            
        # Računanje i spremanje rezultata
        result = func(*args, **kwargs)
        cache[key] = result
        
        return result
        
    # Dodajemo metodu za čišćenje keša
    wrapper.cache_clear = cache.clear
    
    return wrapper

def retry(max_attempts=3, delay=0.1, backoff=2, exceptions=(Exception,)):
    """
    Dekorator koji ponovno pokušava izvršiti funkciju u slučaju specifične greške.
    
    Args:
        max_attempts (int): Maksimalni broj pokušaja
        delay (float): Početna pauza između pokušaja u sekundama
        backoff (float): Faktor povećanja pauze za svaki novi pokušaj
        exceptions (tuple): Tuple klasa iznimki koje se trebaju uhvatiti
        
    Returns:
        Dekorator
        
    Primjer:
        @retry(max_attempts=5, delay=0.2, exceptions=(ValueError, KeyError))
        def funkcija_koja_moze_failati():
            # kod funkcije
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Dohvaćanje imena klase, ako je metoda
            if args and hasattr(args[0], '__class__'):
                class_name = args[0].__class__.__name__
                func_name = f"{class_name}.{func.__name__}"
            else:
                func_name = func.__name__
            
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"Pokušaj {attempt}/{max_attempts} za {func_name} neuspješan: {str(e)}. "
                            f"Ponovni pokušaj za {current_delay:.2f}s."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"Svi pokušaji ({max_attempts}) za {func_name} neuspješni. "
                            f"Posljednja greška: {str(e)}"
                        )
            
            # Ako smo došli ovdje, svi pokušaji su neuspješni
            raise last_exception
            
        return wrapper
    
    return decorator 