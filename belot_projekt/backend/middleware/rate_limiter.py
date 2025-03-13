"""
Middleware za ograničavanje broja zahtjeva u Belot aplikaciji.

Ovaj modul implementira middleware za ograničavanje broja zahtjeva
koje korisnik može poslati u određenom vremenskom periodu. Cilj je
spriječiti preopterećenje servera zbog previše zahtjeva od strane
pojedinačnih korisnika ili automatiziranih botova.
"""

import time
import logging
import hashlib
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.core.cache import cache
from utils.decorators import track_execution_time

logger = logging.getLogger('belot.rate_limiter')


class RateLimiterMiddleware(MiddlewareMixin):
    """
    Middleware koji ograničava broj zahtjeva po korisniku ili IP adresi.
    
    Koristi Redis cache za praćenje broja zahtjeva po korisniku ili IP adresi.
    Ako korisnik prekorači dozvoljeni broj zahtjeva, middleware vraća odgovor
    s HTTP statusom 429 (Too Many Requests).
    """
    
    # Zadani parametri za ograničavanje
    DEFAULT_RATE_LIMIT = 100  # broj zahtjeva
    DEFAULT_RATE_WINDOW = 60  # sekundi
    DEFAULT_RATE_KEY_PREFIX = 'ratelimit'
    
    # Putanje koje su izuzete od ograničenja
    EXEMPT_PATHS = [
        r'^/admin/',          # Django admin
        r'^/static/',         # Statički fajlovi
        r'^/media/',          # Korisnički uploadani fajlovi
        r'^/favicon.ico$',    # Favicon
    ]
    
    def __init__(self, get_response):
        """Inicijalizira middleware s funkcijom get_response."""
        self.get_response = get_response
        
        # Učitaj postavke iz settings.py ako postoje
        self.rate_limit = getattr(settings, 'RATE_LIMIT_REQUESTS', self.DEFAULT_RATE_LIMIT)
        self.rate_window = getattr(settings, 'RATE_LIMIT_WINDOW', self.DEFAULT_RATE_WINDOW)
        self.rate_key_prefix = getattr(settings, 'RATE_LIMIT_KEY_PREFIX', self.DEFAULT_RATE_KEY_PREFIX)
        
        # API-specifična ograničenja (strože za API zahtjeve)
        self.api_rate_limit = getattr(settings, 'API_RATE_LIMIT_REQUESTS', self.rate_limit // 2)
        self.api_rate_window = getattr(settings, 'API_RATE_LIMIT_WINDOW', self.rate_window)
    
    def __call__(self, request):
        """
        Obrađuje zahtjev i provjerava ograničenja.
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            HttpResponse: Odgovor na zahtjev
        """
        # Provjeri je li putanja izuzeta od ograničenja
        if self._is_exempt_path(request.path):
            return self.get_response(request)
        
        # Odaberi odgovarajuće ograničenje ovisno o tipu zahtjeva
        is_api_request = request.path.startswith('/api/')
        rate_limit = self.api_rate_limit if is_api_request else self.rate_limit
        rate_window = self.api_rate_window if is_api_request else self.rate_window
        
        # Generiraj ključ za korisnika ili IP adresu
        client_key = self._get_client_key(request)
        cache_key = f"{self.rate_key_prefix}:{client_key}"
        
        # Dohvati trenutni broj zahtjeva i vremenski period
        now = int(time.time())
        request_data = cache.get(cache_key)
        
        if request_data is None:
            # Prvi zahtjev
            request_data = {
                'count': 1,
                'start_time': now
            }
            cache.set(cache_key, request_data, rate_window)
        else:
            # Provjeri je li vremenski period istekao
            if now - request_data['start_time'] > rate_window:
                # Ako je, resetiraj brojač
                request_data = {
                    'count': 1,
                    'start_time': now
                }
                cache.set(cache_key, request_data, rate_window)
            else:
                # Inače, inkrementiraj brojač
                request_data['count'] += 1
                cache.set(cache_key, request_data, rate_window)
        
        # Provjeri je li broj zahtjeva prekoračen
        if request_data['count'] > rate_limit:
            # Izračunaj vrijeme do isteka ograničenja
            reset_time = request_data['start_time'] + rate_window
            seconds_left = max(0, reset_time - now)
            
            # Logiraj prekoračenje
            logger.warning(
                'Rate limit exceeded for %s: %d requests in %d seconds',
                client_key, request_data['count'], now - request_data['start_time']
            )
            
            # Vrati odgovor s HTTP statusom 429
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'code': 'rate_limit_exceeded',
                'detail': f'You have exceeded the rate limit of {rate_limit} requests per {rate_window} seconds',
                'retry_after': seconds_left
            }, status=429, headers={'Retry-After': str(seconds_left)})
        
        # Nastavi s obradom zahtjeva
        response = self.get_response(request)
        
        # Dodaj Rate-Limit zaglavlja u odgovor
        if is_api_request:
            response['X-RateLimit-Limit'] = str(rate_limit)
            response['X-RateLimit-Remaining'] = str(max(0, rate_limit - request_data['count']))
            response['X-RateLimit-Reset'] = str(request_data['start_time'] + rate_window)
        
        return response
    
    def _get_client_key(self, request):
        """
        Generira ključ za identifikaciju klijenta.
        
        Prioritet:
        1. Autentificirani korisnik
        2. IP adresa
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            str: Ključ za identifikaciju klijenta
        """
        if request.user.is_authenticated:
            return f"user:{request.user.id}"
        
        # Dohvati IP adresu (podržava i proxy/load balancer scenarije)
        ip = self._get_client_ip(request)
        
        # Haširana IP adresa za bolju privatnost u logovima
        hashed_ip = hashlib.md5(ip.encode()).hexdigest()
        return f"ip:{hashed_ip}"
    
    def _get_client_ip(self, request):
        """
        Dohvaća IP adresu klijenta iz zahtjeva.
        
        Uzima u obzir proxy i load balancer scenarije.
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            str: IP adresa klijenta
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Uzmemo prvu IP adresu iz X-Forwarded-For zaglavlja
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip
    
    def _is_exempt_path(self, path):
        """
        Provjerava je li putanja izuzeta od ograničenja.
        
        Args:
            path: Putanja zahtjeva
            
        Returns:
            bool: True ako je putanja izuzeta, False inače
        """
        import re
        return any(re.match(pattern, path) for pattern in self.EXEMPT_PATHS)


class APIThrottleMiddleware(MiddlewareMixin):
    """
    Middleware koji implementira detaljnije ograničenje API zahtjeva.
    
    Ovaj middleware omogućuje različita ograničenja za različite API endpointe,
    kao i različite razine ograničenja za anonimne i autentificirane korisnike.
    """
    
    # Zadana ograničenja za API endpointe
    DEFAULT_THROTTLE_RATES = {
        'anon': '20/minute',      # 20 zahtjeva po minuti za anonimne korisnike
        'user': '60/minute',      # 60 zahtjeva po minuti za autentificirane korisnike
        'game': '120/minute',     # 120 zahtjeva po minuti za game API
        'lobby': '60/minute',     # 60 zahtjeva po minuti za lobby API
        'auth': '10/minute',      # 10 zahtjeva po minuti za auth API
    }
    
    def __init__(self, get_response):
        """Inicijalizira middleware s funkcijom get_response."""
        self.get_response = get_response
        
        # Učitaj postavke iz settings.py ako postoje
        self.throttle_rates = getattr(settings, 'API_THROTTLE_RATES', self.DEFAULT_THROTTLE_RATES)
        
        # Parsiranje stope ograničenja
        self.parsed_rates = {}
        for key, rate in self.throttle_rates.items():
            num, period = rate.split('/')
            num = int(num)
            
            # Pretvori period u sekunde
            if period == 'second':
                period_seconds = 1
            elif period == 'minute':
                period_seconds = 60
            elif period == 'hour':
                period_seconds = 60 * 60
            elif period == 'day':
                period_seconds = 24 * 60 * 60
            else:
                raise ValueError(f"Nepoznati period: {period}")
            
            self.parsed_rates[key] = (num, period_seconds)
    
    def __call__(self, request):
        """
        Obrađuje zahtjev i provjerava ograničenja.
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            HttpResponse: Odgovor na zahtjev
        """
        # Provjeri je li zahtjev upućen API-ju
        if not request.path.startswith('/api/'):
            return self.get_response(request)
        
        # Odaberi odgovarajuću stopu ograničenja
        if request.path.startswith('/api/game/'):
            rate_key = 'game'
        elif request.path.startswith('/api/lobby/'):
            rate_key = 'lobby'
        elif request.path.startswith('/api/auth/'):
            rate_key = 'auth'
        else:
            # Generički API - ovisno o autentikaciji
            rate_key = 'user' if request.user.is_authenticated else 'anon'
        
        # Dohvati stopu ograničenja
        num_requests, period_seconds = self.parsed_rates[rate_key]
        
        # Generiraj ključ za korisnika ili IP adresu
        client_key = self._get_client_key(request)
        cache_key = f"apithrottle:{rate_key}:{client_key}"
        
        # Dohvati trenutni broj zahtjeva i vremenski period
        now = int(time.time())
        request_data = cache.get(cache_key)
        
        if request_data is None:
            # Prvi zahtjev
            request_data = {
                'count': 1,
                'start_time': now
            }
            cache.set(cache_key, request_data, period_seconds)
        else:
            # Provjeri je li vremenski period istekao
            if now - request_data['start_time'] > period_seconds:
                # Ako je, resetiraj brojač
                request_data = {
                    'count': 1,
                    'start_time': now
                }
                cache.set(cache_key, request_data, period_seconds)
            else:
                # Inače, inkrementiraj brojač
                request_data['count'] += 1
                cache.set(cache_key, request_data, period_seconds)
        
        # Provjeri je li broj zahtjeva prekoračen
        if request_data['count'] > num_requests:
            # Izračunaj vrijeme do isteka ograničenja
            reset_time = request_data['start_time'] + period_seconds
            seconds_left = max(0, reset_time - now)
            
            # Logiraj prekoračenje
            logger.warning(
                'API throttle exceeded for %s on %s: %d requests in %d seconds',
                client_key, rate_key, request_data['count'], now - request_data['start_time']
            )
            
            # Vrati odgovor s HTTP statusom 429
            return JsonResponse({
                'error': 'API request throttled',
                'code': 'throttled',
                'detail': f'You have exceeded the rate limit for this endpoint',
                'retry_after': seconds_left
            }, status=429, headers={'Retry-After': str(seconds_left)})
        
        # Nastavi s obradom zahtjeva
        response = self.get_response(request)
        
        # Dodaj Rate-Limit zaglavlja u odgovor
        response['X-RateLimit-Limit'] = str(num_requests)
        response['X-RateLimit-Remaining'] = str(max(0, num_requests - request_data['count']))
        response['X-RateLimit-Reset'] = str(request_data['start_time'] + period_seconds)
        
        return response
    
    def _get_client_key(self, request):
        """
        Generira ključ za identifikaciju klijenta.
        
        Prioritet:
        1. Autentificirani korisnik
        2. IP adresa
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            str: Ključ za identifikaciju klijenta
        """
        if request.user.is_authenticated:
            return f"user:{request.user.id}"
        
        # Dohvati IP adresu (podržava i proxy/load balancer scenarije)
        ip = self._get_client_ip(request)
        
        # Haširana IP adresa za bolju privatnost u logovima
        hashed_ip = hashlib.md5(ip.encode()).hexdigest()
        return f"ip:{hashed_ip}"
    
    def _get_client_ip(self, request):
        """
        Dohvaća IP adresu klijenta iz zahtjeva.
        
        Uzima u obzir proxy i load balancer scenarije.
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            str: IP adresa klijenta
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Uzmemo prvu IP adresu iz X-Forwarded-For zaglavlja
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip