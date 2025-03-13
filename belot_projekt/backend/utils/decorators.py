"""
Dekoratori za Belot aplikaciju.

Ovaj modul definira razne dekoratore koji se mogu koristiti 
za proširenje funkcionalnosti pogleda i drugih funkcija.
"""

import time
import logging
import functools
from typing import Any, Callable, Dict, Optional, Type, Union, List

from django.http import JsonResponse, HttpRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.conf import settings
from django.core.cache import cache, caches
from django.utils import timezone
from django.utils.decorators import method_decorator

logger = logging.getLogger('utils.decorators')


def login_required_ajax(view_func):
    """
    Dekorator koji provjerava je li korisnik prijavljen za AJAX zahtjeve.
    
    Za AJAX zahtjeve šalje JsonResponse s greškom umjesto preusmjeravanja
    na stranicu za prijavu. Za ne-AJAX zahtjeve koristi standardni 
    login_required dekorator.
    
    Args:
        view_func: Funkcija pogleda koja se dekorira
    
    Returns:
        Dekorirana funkcija
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': 'Niste prijavljeni',
                    'redirect': settings.LOGIN_URL
                }, status=401)
            else:
                return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        return view_func(request, *args, **kwargs)
    
    return wrapper


def admin_required(view_func):
    """
    Dekorator koji provjerava je li korisnik administrator.
    
    Args:
        view_func: Funkcija pogleda koja se dekorira
    
    Returns:
        Dekorirana funkcija
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Provjeri je li korisnik prijavljen
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        
        # Provjeri je li korisnik administrator
        if not request.user.is_staff and not request.user.is_superuser:
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': 'Nemate dozvolu za pristup ovoj stranici'
                }, status=403)
            else:
                from django.contrib import messages
                messages.error(request, 'Nemate dozvolu za pristup ovoj stranici')
                return redirect('home')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def throttle_request(rate_limit: int, duration: int = 60, scope: str = 'default', cache_name: str = 'default'):
    """
    Dekorator koji ograničava broj zahtjeva za funkciju.
    
    Koristi Redis cache za praćenje broja zahtjeva.
    
    Args:
        rate_limit: Maksimalni broj zahtjeva u vremenskom razdoblju
        duration: Trajanje vremenskog razdoblja u sekundama (zadano: 60)
        scope: Opseg ograničenja (zadano: 'default')
        cache_name: Naziv cache backneda za korištenje (zadano: 'default')
    
    Returns:
        Dekorator za funkciju
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Koristi specifični cache backend
            throttle_cache = caches[cache_name]
            
            # Generiraj ključ za cache
            # Za ulogiranog korisnika koristi ID, inače IP adresu
            if request.user.is_authenticated:
                key_base = f"user_{request.user.id}"
            else:
                key_base = f"ip_{_get_client_ip(request)}"
            
            cache_key = f"throttle_{scope}_{key_base}"
            
            # Dohvati trenutni broj zahtjeva i vrijeme
            throttle_data = throttle_cache.get(cache_key)
            now = time.time()
            
            if throttle_data is None:
                # Prvi zahtjev
                throttle_data = {
                    'count': 1,
                    'reset': now + duration
                }
                throttle_cache.set(cache_key, throttle_data, duration)
            else:
                # Provjeri je li vrijeme isteklo
                if now > throttle_data['reset']:
                    # Resetiraj brojač
                    throttle_data = {
                        'count': 1,
                        'reset': now + duration
                    }
                    throttle_cache.set(cache_key, throttle_data, duration)
                else:
                    # Provjeri je li broj zahtjeva prekoračen
                    if throttle_data['count'] >= rate_limit:
                        # Izračunaj vrijeme do resetiranja
                        retry_after = int(throttle_data['reset'] - now)
                        
                        # Logiraj prekoračenje
                        logger.warning(
                            f"Ograničenje zahtjeva prekoračeno: {key_base} ({throttle_data['count']}/{rate_limit})"
                        )
                        
                        # Vrati odgovor s greškom
                        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                        if is_ajax:
                            return JsonResponse({
                                'success': False,
                                'error': 'Previše zahtjeva, pokušajte kasnije',
                                'retry_after': retry_after
                            }, status=429, headers={'Retry-After': str(retry_after)})
                        else:
                            from django.contrib import messages
                            messages.warning(request, 'Previše zahtjeva, pokušajte kasnije')
                            return redirect('home')
                    
                    # Povećaj brojač
                    throttle_data['count'] += 1
                    throttle_cache.set(cache_key, throttle_data, int(throttle_data['reset'] - now))
            
            # Nastavi s izvršavanjem pogleda
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def track_execution_time(view_func):
    """
    Dekorator koji prati vrijeme izvršavanja funkcije.
    
    Mjeri i logira vrijeme potrebno za izvršavanje funkcije.
    
    Args:
        view_func: Funkcija koja se dekorira
    
    Returns:
        Dekorirana funkcija
    """
    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        # Zabilježi početno vrijeme
        start_time = time.time()
        
        # Izvrši funkciju
        result = view_func(*args, **kwargs)
        
        # Izračunaj trajanje
        duration = time.time() - start_time
        
        # Logiraj trajanje
        logger.info(f"Izvršavanje {view_func.__name__} trajalo je {duration:.4f} sekundi")
        
        # Ako je HTTP odgovor, dodaj zaglavlje s vremenom izvršavanja
        if isinstance(result, HttpResponse) and not settings.PRODUCTION:
            result['X-Execution-Time'] = f"{duration:.4f}s"
        
        return result
    
    return wrapper


class cached_property:
    """
    Dekorator koji pretvara metodu objekta u svojstvo sa cachiranjem.
    
    Vrijednost svojstva se računa samo jednom i sprema se u instancu objekta.
    Slično Django-ovom cached_property ali s dodatnim opcijama.
    """
    
    def __init__(self, func, ttl=None):
        """
        Inicijalizacija dekoratora.
        
        Args:
            func: Funkcija koja se dekorira
            ttl: Vrijeme života (Time To Live) u sekundama (None = zauvijek)
        """
        self.func = func
        self.ttl = ttl
        self.__doc__ = func.__doc__
        self.__name__ = func.__name__
        self.__module__ = func.__module__
    
    def __get__(self, instance, owner=None):
        """
        Dohvat vrijednosti svojstva.
        
        Args:
            instance: Instanca objekta
            owner: Klasa objekta
        
        Returns:
            Vrijednost svojstva
        """
        if instance is None:
            return self
        
        # Generiraj ključ atributa
        attr_key = f"_{self.__name__}"
        ttl_key = f"{attr_key}_ttl"
        
        # Provjeri je li vrijednost već izračunata i nije istekla
        if hasattr(instance, attr_key):
            # Ako ima TTL, provjeri je li istekao
            if self.ttl is not None and hasattr(instance, ttl_key):
                if time.time() > getattr(instance, ttl_key):
                    # TTL je istekao, izbriši cached vrijednost
                    delattr(instance, attr_key)
                    delattr(instance, ttl_key)
                else:
                    # TTL nije istekao, vrati cached vrijednost
                    return getattr(instance, attr_key)
            else:
                # Nema TTL, vrati cached vrijednost
                return getattr(instance, attr_key)
        
        # Izračunaj vrijednost
        value = self.func(instance)
        
        # Spremi vrijednost u instancu
        setattr(instance, attr_key, value)
        
        # Ako ima TTL, spremi vrijeme isteka
        if self.ttl is not None:
            setattr(instance, ttl_key, time.time() + self.ttl)
        
        return value


def require_ajax(view_func):
    """
    Dekorator koji provjerava je li zahtjev AJAX.
    
    Ako zahtjev nije AJAX, vraća grešku 400.
    
    Args:
        view_func: Funkcija pogleda koja se dekorira
    
    Returns:
        Dekorirana funkcija
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if not is_ajax:
            return JsonResponse({
                'success': False,
                'error': 'Ovaj endpoint podržava samo AJAX zahtjeve'
            }, status=400)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_post(view_func):
    """
    Dekorator koji provjerava je li zahtjev POST.
    
    Ako zahtjev nije POST, vraća grešku 405.
    
    Args:
        view_func: Funkcija pogleda koja se dekorira
    
    Returns:
        Dekorirana funkcija
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.method != 'POST':
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': 'Ovaj endpoint podržava samo POST zahtjeve'
                }, status=405)
            else:
                return HttpResponse(
                    'Ovaj endpoint podržava samo POST zahtjeve',
                    status=405,
                    headers={'Allow': 'POST'}
                )
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_websocket(view_func):
    """
    Dekorator koji provjerava je li zahtjev WebSocket.
    
    Ovaj dekorator se koristi s Django Channels consumer-ima.
    
    Args:
        view_func: Funkcija koja se dekorira
    
    Returns:
        Dekorirana funkcija
    """
    @functools.wraps(view_func)
    async def wrapper(self, *args, **kwargs):
        if not self.scope.get('type') == 'websocket':
            await self.close()
            return
        
        return await view_func(self, *args, **kwargs)
    
    return wrapper


def cache_with_key(timeout=60, cache_name='default', vary_on=None):
    """
    Dekorator za cachiranje rezultata funkcije s prilagodljivim ključem.
    
    Args:
        timeout: Trajanje cachea u sekundama
        cache_name: Ime cache backneda
        vary_on: Funkcija koja generira ključ iz argumenata
        
    Returns:
        Dekorirana funkcija
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Koristi specifični cache backend
            cache_backend = caches[cache_name]
            
            # Generiraj ključ
            if vary_on:
                key = vary_on(*args, **kwargs)
            else:
                # Zadani ključ je ime funkcije + hash argumenata
                key = f"{func.__module__}.{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Pokušaj dohvatiti rezultat iz cachea
            result = cache_backend.get(key)
            if result is not None:
                return result
            
            # Ako nije u cacheu, izračunaj rezultat
            result = func(*args, **kwargs)
            
            # Spremi rezultat u cache
            cache_backend.set(key, result, timeout)
            
            return result
        return wrapper
    return decorator


def _get_client_ip(request):
    """
    Pomoćna funkcija za dohvaćanje IP adrese klijenta.
    
    Args:
        request: HTTP zahtjev
    
    Returns:
        IP adresa klijenta
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Uzmi prvu IP adresu (klijentsku)
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    
    return ip