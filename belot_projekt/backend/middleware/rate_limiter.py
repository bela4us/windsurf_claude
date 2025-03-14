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
import json
from datetime import datetime

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext as _
from utils.decorators import track_execution_time

logger = logging.getLogger('belot.rate_limiter')


class RateLimiterMiddleware(MiddlewareMixin):
    """
    Middleware koji ograničava broj zahtjeva po korisniku ili IP adresi.
    
    Koristi Redis cache za praćenje broja zahtjeva po korisniku ili IP adresi.
    Ako korisnik prekorači dozvoljeni broj zahtjeva, middleware vraća odgovor
    s HTTP statusom 429 (Too Many Requests).
    
    Podržava različite limite za različite vrste zahtjeva (API/web, autenticirani/anonimni)
    i dodaje odgovarajuća HTTP zaglavlja u skladu s najboljim praksama.
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
        r'^/health-check/$',  # Endpoint za provjeru stanja
    ]
    
    # Viši limiti za posebne endpointe (npr. prijava, registracija)
    AUTH_ENDPOINTS = [
        r'^/api/v\d+/auth/login/',
        r'^/api/auth/login/',
        r'^/api/v\d+/auth/register/',
        r'^/api/auth/register/',
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
        
        # Posebna ograničenja za autentikacijske endpointe (strože)
        self.auth_rate_limit = getattr(settings, 'AUTH_RATE_LIMIT_REQUESTS', 5)
        self.auth_rate_window = getattr(settings, 'AUTH_RATE_LIMIT_WINDOW', 60)
        
        # Posebna ograničenja za authenticated vs anonymous korisnike
        self.auth_user_multiplier = getattr(settings, 'AUTH_USER_LIMIT_MULTIPLIER', 3)
        
        # Cache expiry grace period - dodajemo ovo vrijeme da cache ne bi istekao prerano
        self.cache_grace_period = 10
    
    @track_execution_time
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
        is_api_request = self._is_api_request(request.path)
        is_auth_endpoint = self._is_auth_endpoint(request.path)
        is_authenticated = request.user.is_authenticated
        
        # Odabir odgovarajućih limita na temelju vrste zahtjeva
        if is_auth_endpoint:
            rate_limit = self.auth_rate_limit
            rate_window = self.auth_rate_window
        elif is_api_request:
            rate_limit = self.api_rate_limit
            rate_window = self.api_rate_window
        else:
            rate_limit = self.rate_limit
            rate_window = self.rate_window
        
        # Povećaj limit za autenticirane korisnike (osim za auth endpointe)
        if is_authenticated and not is_auth_endpoint:
            rate_limit = rate_limit * self.auth_user_multiplier
        
        # Generiraj ključ za korisnika ili IP adresu
        client_key = self._get_client_key(request)
        endpoint_type = 'auth' if is_auth_endpoint else ('api' if is_api_request else 'web')
        cache_key = f"{self.rate_key_prefix}:{endpoint_type}:{client_key}"
        
        # Dohvati trenutni broj zahtjeva i vremenski period
        now = int(time.time())
        request_data = cache.get(cache_key)
        
        if request_data is None:
            # Prvi zahtjev
            request_data = {
                'count': 1,
                'start_time': now,
                'requests': [now]  # Pratimo sve zahtjeve za analizu uzoraka
            }
            cache.set(cache_key, request_data, rate_window + self.cache_grace_period)
        else:
            # Provjeri je li vremenski period istekao
            elapsed_time = now - request_data['start_time']
            if elapsed_time > rate_window:
                # Ako je, resetiraj brojač
                request_data = {
                    'count': 1,
                    'start_time': now,
                    'requests': [now]
                }
                cache.set(cache_key, request_data, rate_window + self.cache_grace_period)
            else:
                # Ako nije, provjeri je li prekoračen limit
                if request_data['count'] >= rate_limit:
                    # Prekoračen limit - analiziraj uzorak zahtjeva za potencijalne DoS napade
                    self._analyze_request_pattern(request_data, client_key, endpoint_type, request)
                    
                    # Izračunaj kada će limit biti resetiran
                    reset_seconds = rate_window - elapsed_time
                    reset_time = int(time.time() + reset_seconds)
                    
                    # Logiraj prekoračenje
                    logger.warning(
                        f"Rate limit exceeded: {client_key} ({request_data['count']} requests in {elapsed_time}s)"
                    )
                    
                    # Vrati odgovor s informacijama o limitu
                    return self._get_rate_limit_response(rate_limit, reset_time, reset_seconds)
                
                # Inače povećaj brojač i spremi vrijeme zahtjeva
                request_data['count'] += 1
                request_data['requests'].append(now)
                
                # Ograniči listu zahtjeva na zadnjih 100 za analizu uzoraka
                if len(request_data['requests']) > 100:
                    request_data['requests'] = request_data['requests'][-100:]
                
                cache.set(cache_key, request_data, rate_window + self.cache_grace_period)
        
        # Prosljeđujemo zahtjev i dodajemo informacije o limitu u odgovor
        response = self.get_response(request)
        
        # Dodaj informacije o limitu u HTTP zaglavlja
        remaining = max(0, rate_limit - request_data['count'])
        reset_time = request_data['start_time'] + rate_window
        self._add_rate_limit_headers(response, rate_limit, remaining, reset_time)
        
        return response
    
    def _get_client_key(self, request):
        """
        Generira jedinstveni ključ za korisnika ili IP adresu.
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            str: Jedinstveni ključ za identificiranje klijenta
        """
        # Ako je korisnik autenticiran, koristi ID korisnika
        if request.user.is_authenticated:
            return f"user:{request.user.id}"
        
        # Inače koristi IP adresu
        ip = self._get_client_ip(request)
        # Hashiranje IP adrese za privatnost
        return f"ip:{hashlib.md5(ip.encode()).hexdigest()}"
    
    def _get_client_ip(self, request):
        """
        Dohvaća IP adresu klijenta iz zahtjeva.
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            str: IP adresa
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip
    
    def _is_api_request(self, path):
        """
        Provjerava je li zahtjev upućen API-ju.
        
        Args:
            path: Putanja zahtjeva
            
        Returns:
            bool: True ako je API zahtjev, False inače
        """
        return path.startswith('/api/')
    
    def _is_exempt_path(self, path):
        """
        Provjerava je li putanja izuzeta od ograničenja.
        
        Args:
            path: Putanja zahtjeva
            
        Returns:
            bool: True ako je putanja izuzeta, False inače
        """
        import re
        for pattern in self.EXEMPT_PATHS:
            if re.match(pattern, path):
                return True
        return False
    
    def _is_auth_endpoint(self, path):
        """
        Provjerava je li putanja autentikacijski endpoint.
        
        Args:
            path: Putanja zahtjeva
            
        Returns:
            bool: True ako je autentikacijski endpoint, False inače
        """
        import re
        for pattern in self.AUTH_ENDPOINTS:
            if re.match(pattern, path):
                return True
        return False
    
    def _get_rate_limit_response(self, limit, reset_time, reset_seconds):
        """
        Stvara odgovor za prekoračeni limit.
        
        Args:
            limit: Maksimalno dozvoljeni broj zahtjeva
            reset_time: Unix timestamp kada će limit biti resetiran
            reset_seconds: Sekunde do reseta limita
            
        Returns:
            JsonResponse: Odgovor s informacijama o limitu
        """
        response = JsonResponse({
            'status': 'error',
            'code': 'rate_limit_exceeded',
            'message': _('Prekoračen je maksimalni broj zahtjeva. Pokušajte ponovno kasnije.'),
            'details': {
                'limit': limit,
                'reset': datetime.fromtimestamp(reset_time).isoformat(),
                'reset_seconds': reset_seconds,
            }
        }, status=429)
        
        # Dodaj standardne rate-limit headere
        self._add_rate_limit_headers(response, limit, 0, reset_time)
        
        # Dodaj Retry-After header (standard za 429)
        response['Retry-After'] = str(int(reset_seconds))
        
        return response
    
    def _add_rate_limit_headers(self, response, limit, remaining, reset_time):
        """
        Dodaje standardne rate-limit headere u odgovor.
        
        Args:
            response: HTTP odgovor
            limit: Maksimalno dozvoljeni broj zahtjeva
            remaining: Preostali broj zahtjeva
            reset_time: Unix timestamp kada će limit biti resetiran
            
        Returns:
            None
        """
        response['X-RateLimit-Limit'] = str(limit)
        response['X-RateLimit-Remaining'] = str(remaining)
        response['X-RateLimit-Reset'] = str(int(reset_time))
    
    def _analyze_request_pattern(self, request_data, client_key, endpoint_type, request):
        """
        Analizira uzorak zahtjeva za potencijalne DoS napade.
        
        Args:
            request_data: Podaci o zahtjevima
            client_key: Ključ klijenta
            endpoint_type: Tip endpointa (auth, api, web)
            request: HTTP zahtjev
            
        Returns:
            None
        """
        # Izračunaj vremenske razmake između zahtjeva
        if len(request_data['requests']) < 3:
            return
            
        intervals = []
        for i in range(1, len(request_data['requests'])):
            intervals.append(request_data['requests'][i] - request_data['requests'][i-1])
        
        # Izračunaj standardnu devijaciju intervala
        import statistics
        try:
            mean_interval = statistics.mean(intervals)
            stdev_interval = statistics.stdev(intervals) if len(intervals) > 1 else 0
            
            # Ako je standardna devijacija mala, a srednji interval vrlo mali,
            # to može ukazivati na automatiziran napad
            if (stdev_interval < 0.1 * mean_interval and mean_interval < 1.0 and 
                len(request_data['requests']) > 10):
                client_ip = self._get_client_ip(request)
                logger.warning(
                    f"Potential DoS attack detected: {client_key} from IP {client_ip} on {endpoint_type} "
                    f"endpoint (mean_interval={mean_interval:.3f}s, stdev={stdev_interval:.3f}s, "
                    f"requests={len(request_data['requests'])})"
                )
                
                # Mogućnost da se ovdje dodaju dodatne mjere kao što je privremeno blokiranje
                # IP adrese putem vanjskog sustava ili duže vrijeme čekanja za ovog klijenta
        except Exception as e:
            logger.error(f"Error analyzing request pattern: {str(e)}")


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