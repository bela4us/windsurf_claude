"""
Middleware za autentikaciju u Belot aplikaciji.

Ovaj modul implementira middleware za obradu autentikacijskih tokena
koji omogućuju pristup API-ju i WebSocket konekcijama. Glavni zadatak
middleware-a je provjera valjanosti tokena i dodavanje informacije o
korisniku u request objekt.
"""

import logging
import re
import json
import time
import hashlib
from datetime import datetime, timedelta

from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from django.core.cache import cache

from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

from rest_framework.authtoken.models import Token
from jwt import decode as jwt_decode, encode as jwt_encode
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from utils.decorators import track_execution_time

User = get_user_model()
logger = logging.getLogger('belot.auth_middleware')


class TokenAuthMiddleware(MiddlewareMixin):
    """
    Middleware koji provjerava autentikacijski token u HTTP zahtjevima.
    
    Ovaj middleware provjerava prisutnost i valjanost tokena u zahtjevima
    upućenim API rutama. Ako je token valjan, middleware postavlja
    informaciju o autentificiranom korisniku u request objekt.
    
    Podržava različite vrste tokena:
    - Token Authentication (standardni Django REST Framework token)
    - JWT tokenima (s provjerom isteka i potpisa)
    - Token rotacija za poboljšanje sigurnosti
    - Blacklisting poništenih tokena
    """
    
    # Uzorci putanja za koje ovaj middleware ne provjerava token
    EXEMPT_PATHS = [
        r'^/admin/',          # Django admin
        r'^/api/auth/',       # Autentikacijske rute
        r'^/static/',         # Statički fajlovi
        r'^/media/',          # Korisnički uploadani fajlovi
        r'^/$',               # Početna stranica
        r'^/favicon.ico$',    # Favicon
        r'^/health-check/$',  # Endpoint za provjeru stanja
    ]
    
    # Prefiks za blacklistane tokene u cacheu
    TOKEN_BLACKLIST_PREFIX = 'token_blacklist:'
    
    # Period rotacije tokena (u sekundama)
    TOKEN_ROTATION_PERIOD = 3600 * 24  # 24 sata
    
    def __init__(self, get_response):
        """Inicijalizira middleware s funkcijom get_response."""
        self.get_response = get_response
        
        # Učitaj postavke iz settings.py
        self.jwt_secret = getattr(settings, 'JWT_SECRET_KEY', settings.SECRET_KEY)
        self.jwt_algorithm = getattr(settings, 'JWT_ALGORITHM', 'HS256')
        self.jwt_expiration = getattr(settings, 'JWT_EXPIRATION_DELTA', 60 * 60 * 24)  # 1 dan
        self.token_rotation = getattr(settings, 'TOKEN_ROTATION_ENABLED', True)
        self.token_rotation_period = getattr(settings, 'TOKEN_ROTATION_PERIOD', self.TOKEN_ROTATION_PERIOD)
        
        # Postavke za spremanje informacija o korisničkim sesijama i IP adresama
        self.track_session_info = getattr(settings, 'TRACK_SESSION_INFO', True)
        self.track_suspicious_activity = getattr(settings, 'TRACK_SUSPICIOUS_ACTIVITY', True)
    
    @track_execution_time
    def __call__(self, request):
        """
        Obrađuje zahtjev i provjerava token.
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            HttpResponse: Odgovor na zahtjev
        """
        # Provjeri je li putanja izuzeta od provjere tokena
        if self._is_exempt_path(request.path):
            return self.get_response(request)
        
        # Provjeri je li API zahtjev
        if not self._is_api_request(request):
            return self.get_response(request)
        
        # Dohvati token iz zaglavlja
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header:
            # Token nije prisutan u zahtjevu - nastavi bez autentikacije
            return self.get_response(request)
        
        # Raspodjeli po tipu tokena
        if auth_header.startswith('Bearer '):
            # JWT token
            token = auth_header.split(' ', 1)[1].strip()
            user, new_token = self._get_user_from_jwt(token, request)
        elif auth_header.startswith('Token '):
            # Token Authentication
            token = auth_header.split(' ', 1)[1].strip()
            user, new_token = self._get_user_from_token(token, 'token', request)
        else:
            # Nepoznata shema autentikacije
            logger.warning(f"Unknown authentication scheme: {auth_header.split(' ', 1)[0]}")
            return self.get_response(request)
        
        # Postavi korisnika u request objekt
        request.user = user
        
        # Obradi zahtjev
        response = self.get_response(request)
        
        # Ako je generiran novi token zbog rotacije, dodaj ga u odgovor
        if new_token:
            if isinstance(new_token, dict):
                # JWT token
                response['X-New-Token'] = new_token['access']
                response['X-New-Token-Expiry'] = new_token['expiry']
            else:
                # Token Authentication
                response['X-New-Token'] = new_token
        
        return response
    
    def _get_user_from_jwt(self, token, request):
        """
        Dohvaća korisnika iz JWT tokena.
        
        Args:
            token: JWT token
            request: HTTP zahtjev
            
        Returns:
            tuple: (User objekt, novi token ako je potreban)
        """
        try:
            # Dekodiraj token
            payload = jwt_decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            user_id = payload.get('user_id')
            
            # Provjeri je li token na blacklisti
            if self._is_token_blacklisted(token):
                logger.warning(f"Blacklisted JWT token used: {self._mask_token(token)}")
                return AnonymousUser(), None
            
            # Provjeri vrijeme isteka
            exp = payload.get('exp')
            if exp and int(time.time()) > exp:
                # Token je istekao
                logger.debug(f"Expired JWT token: {self._mask_token(token)}")
                return AnonymousUser(), None
            
            try:
                user = User.objects.get(pk=user_id)
                
                # Provjeri je li korisnički račun aktivan
                if not user.is_active:
                    logger.warning(f"Inactive user attempted to authenticate: {user.username}")
                    return AnonymousUser(), None
                
                # Provjeri je li došlo vrijeme za rotaciju tokena
                if self.token_rotation and self._should_rotate_token(payload):
                    new_token = self._generate_jwt_token(user)
                    self._blacklist_token(token)
                    return user, new_token
                
                # Provjeri za sumnjive aktivnosti ako je omogućeno
                if self.track_suspicious_activity:
                    self._check_for_suspicious_activity(user, request, payload)
                
                # Spremi informacije o sesiji ako je omogućeno
                if self.track_session_info:
                    self._update_session_info(user, request, payload)
                
                return user, None
            except User.DoesNotExist:
                logger.warning(f"JWT token with non-existent user ID: {user_id}")
                return AnonymousUser(), None
                
        except ExpiredSignatureError:
            logger.debug(f"Expired JWT signature: {self._mask_token(token)}")
            return AnonymousUser(), None
        except InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {self._mask_token(token)}, error: {str(e)}")
            return AnonymousUser(), None
    
    def _get_user_from_token(self, token, token_type, request):
        """
        Dohvaća korisnika iz Token Authentication tokena.
        
        Args:
            token: Token string
            token_type: Tip tokena ('token')
            request: HTTP zahtjev
            
        Returns:
            tuple: (User objekt, novi token ako je potreban)
        """
        try:
            # Provjeri je li token na blacklisti
            if self._is_token_blacklisted(token):
                logger.warning(f"Blacklisted token used: {self._mask_token(token)}")
                return AnonymousUser(), None
            
            # Dohvati token iz baze
            token_obj = Token.objects.select_related('user').get(key=token)
            user = token_obj.user
            
            # Provjeri je li korisnički račun aktivan
            if not user.is_active:
                logger.warning(f"Inactive user attempted to authenticate: {user.username}")
                return AnonymousUser(), None
            
            # Provjeri je li došlo vrijeme za rotaciju tokena
            if self.token_rotation and self._should_rotate_drf_token(token_obj):
                # Stvori novi token
                # Prvo izbrišimo stari token (u transakciji)
                old_token_key = token_obj.key
                token_obj.delete()
                
                # Zatim stvorimo novi token
                new_token = Token.objects.create(user=user)
                
                # Dodaj stari token na blacklistu
                self._blacklist_token(old_token_key)
                
                return user, new_token.key
            
            # Provjeri za sumnjive aktivnosti ako je omogućeno
            if self.track_suspicious_activity:
                self._check_for_suspicious_activity(user, request)
            
            # Spremi informacije o sesiji ako je omogućeno
            if self.track_session_info:
                self._update_session_info(user, request)
            
            return user, None
            
        except Token.DoesNotExist:
            logger.warning(f"Non-existent token used: {self._mask_token(token)}")
            return AnonymousUser(), None
    
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
        Provjerava je li putanja izuzeta od provjere tokena.
        
        Args:
            path: Putanja zahtjeva
            
        Returns:
            bool: True ako je putanja izuzeta, False inače
        """
        for pattern in self.EXEMPT_PATHS:
            if re.match(pattern, path):
                return True
        return False
    
    def _is_token_blacklisted(self, token):
        """
        Provjerava je li token na blacklisti.
        
        Args:
            token: Token za provjeru
            
        Returns:
            bool: True ako je token na blacklisti, False inače
        """
        token_hash = self._hash_token(token)
        cache_key = f"{self.TOKEN_BLACKLIST_PREFIX}{token_hash}"
        return cache.get(cache_key) is not None
    
    def _blacklist_token(self, token):
        """
        Dodaje token na blacklistu.
        
        Args:
            token: Token za dodavanje na blacklistu
            
        Returns:
            None
        """
        token_hash = self._hash_token(token)
        cache_key = f"{self.TOKEN_BLACKLIST_PREFIX}{token_hash}"
        # Spremi na blacklistu na period koji je dulji od isteka tokena
        cache.set(cache_key, 1, self.jwt_expiration * 2)
    
    def _hash_token(self, token):
        """
        Hashira token za sigurnije spremanje na blacklistu.
        
        Args:
            token: Token za hashiranje
            
        Returns:
            str: Haširan token
        """
        return hashlib.sha256(token.encode()).hexdigest()
    
    def _mask_token(self, token):
        """
        Maskira token za sigurnije logiranje.
        
        Args:
            token: Token za maskiranje
            
        Returns:
            str: Maskirani token
        """
        if len(token) <= 10:
            return "***"
        return token[:6] + "..." + token[-4:]
    
    def _should_rotate_token(self, payload):
        """
        Provjerava je li vrijeme za rotaciju JWT tokena.
        
        Args:
            payload: JWT payload
            
        Returns:
            bool: True ako je vrijeme za rotaciju, False inače
        """
        # Provjeri vrijeme stvaranja tokena
        iat = payload.get('iat')
        if not iat:
            return False
        
        # Provjeri je li prošlo više od TOKEN_ROTATION_PERIOD sekundi
        return int(time.time()) - iat > self.token_rotation_period
    
    def _should_rotate_drf_token(self, token_obj):
        """
        Provjerava je li vrijeme za rotaciju DRF tokena.
        
        Args:
            token_obj: Token objekt
            
        Returns:
            bool: True ako je vrijeme za rotaciju, False inače
        """
        if not hasattr(token_obj, 'created'):
            return False
        
        # Izračunaj koliko je vremena prošlo od stvaranja tokena
        time_since_creation = timezone.now() - token_obj.created
        return time_since_creation.total_seconds() > self.token_rotation_period
    
    def _generate_jwt_token(self, user):
        """
        Generira novi JWT token za korisnika.
        
        Args:
            user: User objekt
            
        Returns:
            dict: Dictionary s novim tokenom i vremenom isteka
        """
        now = int(time.time())
        expiry = now + self.jwt_expiration
        
        payload = {
            'user_id': user.pk,
            'username': user.username,
            'exp': expiry,
            'iat': now,
            'jti': hashlib.md5(f"{now}:{user.pk}:{user.last_login if user.last_login else ''}".encode()).hexdigest()
        }
        
        token = jwt_encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        
        return {
            'access': token,
            'expiry': datetime.fromtimestamp(expiry).isoformat()
        }
    
    def _check_for_suspicious_activity(self, user, request, payload=None):
        """
        Provjerava ima li sumnjivih aktivnosti u korisničkoj sesiji.
        
        Args:
            user: User objekt
            request: HTTP zahtjev
            payload: JWT payload (opcijski)
            
        Returns:
            None
        """
        try:
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Dohvati prethodne sesije korisnika
            cache_key = f"user_sessions:{user.pk}"
            sessions = cache.get(cache_key, [])
            
            # Provjeri za nagle promjene u IP adresi ili korisničkom agentu
            if sessions:
                last_session = sessions[-1]
                if (ip_address and last_session.get('ip') and 
                        ip_address != last_session.get('ip') and 
                        not self._is_similar_ip(ip_address, last_session.get('ip'))):
                    logger.warning(
                        f"Suspicious activity: User {user.username} accessed from new IP. "
                        f"Old: {last_session.get('ip')}, New: {ip_address}"
                    )
                
                if (user_agent and last_session.get('user_agent') and 
                        user_agent != last_session.get('user_agent')):
                    logger.warning(
                        f"Suspicious activity: User {user.username} accessed with new user agent. "
                        f"Old: {last_session.get('user_agent')}, New: {user_agent}"
                    )
        except Exception as e:
            logger.error(f"Error checking for suspicious activity: {str(e)}")
    
    def _update_session_info(self, user, request, payload=None):
        """
        Ažurira informacije o korisničkoj sesiji.
        
        Args:
            user: User objekt
            request: HTTP zahtjev
            payload: JWT payload (opcijski)
            
        Returns:
            None
        """
        try:
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Dohvati prethodne sesije korisnika
            cache_key = f"user_sessions:{user.pk}"
            sessions = cache.get(cache_key, [])
            
            # Dodaj novu sesiju
            new_session = {
                'timestamp': timezone.now().isoformat(),
                'ip': ip_address,
                'user_agent': user_agent,
                'path': request.path
            }
            
            # Ograniči broj sesija koje čuvamo
            sessions.append(new_session)
            if len(sessions) > 10:
                sessions = sessions[-10:]
            
            # Spremi ažurirane sesije
            cache.set(cache_key, sessions, 60 * 60 * 24 * 7)  # 7 dana
        except Exception as e:
            logger.error(f"Error updating session info: {str(e)}")
    
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
    
    def _is_similar_ip(self, ip1, ip2):
        """
        Provjerava jesu li dvije IP adrese slične (iz istog raspona).
        
        Args:
            ip1: Prva IP adresa
            ip2: Druga IP adresa
            
        Returns:
            bool: True ako su IP adrese slične, False inače
        """
        try:
            # Jednostavna provjera za IPv4 adrese
            ip1_parts = ip1.split('.')
            ip2_parts = ip2.split('.')
            
            # Ako se prva 3 dijela podudaraju, IP adrese su vjerojatno u istoj mreži
            return ip1_parts[:3] == ip2_parts[:3]
        except:
            return False


class WebSocketTokenAuthMiddleware(BaseMiddleware):
    """
    Middleware za autentikaciju WebSocket konekcija.
    
    Provjerava autentikacijski token u WebSocket zahtjevima
    i dodaje informaciju o korisniku u scope.
    """
    
    def __init__(self, inner):
        """Inicijalizira middleware."""
        super().__init__(inner)
        
        # Učitaj postavke iz settings.py
        self.jwt_secret = getattr(settings, 'JWT_SECRET_KEY', settings.SECRET_KEY)
        self.jwt_algorithm = getattr(settings, 'JWT_ALGORITHM', 'HS256')
    
    async def __call__(self, scope, receive, send):
        """
        Obrađuje WebSocket zahtjev i provjerava token.
        
        Args:
            scope: WebSocket scope
            receive: Async funkcija za primanje poruka
            send: Async funkcija za slanje poruka
            
        Returns:
            None
        """
        # Izvadi token iz query stringa
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = dict(re.findall(r'([^=&]+)=([^&]*)', query_string))
        
        token = query_params.get('token')
        
        if token:
            # Dohvati korisnika iz tokena
            scope['user'] = await self._get_user_from_token(token)
        else:
            # Bez tokena, korisnik je anoniman
            scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)
    
    @database_sync_to_async
    def _get_user_from_token(self, token):
        """
        Dohvaća korisnika iz tokena.
        
        Args:
            token: Token za dekodiranje
            
        Returns:
            User: Korisnički objekt ili AnonymousUser
        """
        # Prvo pokušaj s JWT tokenom
        try:
            payload = jwt_decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            user_id = payload.get('user_id')
            
            # Provjeri je li token na blacklisti (implementacija bi trebala biti prilagođena)
            # Ovdje koristimo jednostavnu implementaciju
            cache_key = f"token_blacklist:{hashlib.sha256(token.encode()).hexdigest()}"
            if cache.get(cache_key):
                logger.warning(f"Blacklisted JWT token used for WebSocket: {token[:6]}...")
                return AnonymousUser()
                
            # Provjeri istekao li je token
            exp = payload.get('exp')
            if exp and int(time.time()) > exp:
                logger.debug(f"Expired JWT token used for WebSocket: {token[:6]}...")
                return AnonymousUser()
            
            try:
                return User.objects.get(pk=user_id, is_active=True)
            except User.DoesNotExist:
                logger.warning(f"JWT token with non-existent user ID: {user_id}")
                return AnonymousUser()
        
        except (InvalidTokenError, ExpiredSignatureError) as e:
            # Nije JWT token, pokušaj s DRF Token Authentication
            try:
                token_obj = Token.objects.select_related('user').get(key=token)
                if token_obj.user.is_active:
                    return token_obj.user
                else:
                    logger.warning(f"Inactive user attempted WebSocket connection: {token_obj.user.username}")
                    return AnonymousUser()
            except Token.DoesNotExist:
                logger.warning(f"Invalid token used for WebSocket: {token[:6] if len(token) > 6 else token}...")
                return AnonymousUser()
        except Exception as e:
            logger.error(f"Error authenticating WebSocket: {str(e)}")
            return AnonymousUser()


def TokenAuthMiddlewareStack(inner):
    """
    Pomoćna funkcija za dodavanje TokenAuthMiddleware u Channels middleware stack.
    
    Args:
        inner: Unutarnji middleware
        
    Returns:
        Middleware stack s dodanim TokenAuthMiddleware
    """
    return WebSocketTokenAuthMiddleware(AuthMiddlewareStack(inner))