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
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from rest_framework.authtoken.models import Token
from jwt import decode as jwt_decode
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

User = get_user_model()
logger = logging.getLogger('belot.auth_middleware')


class TokenAuthMiddleware(MiddlewareMixin):
    """
    Middleware koji provjerava autentikacijski token u HTTP zahtjevima.
    
    Ovaj middleware provjerava prisutnost i valjanost tokena u zahtjevima
    upućenim API rutama. Ako je token valjan, middleware postavlja
    informaciju o autentificiranom korisniku u request objekt.
    """
    
    # Uzorci putanja za koje ovaj middleware ne provjerava token
    EXEMPT_PATHS = [
        r'^/admin/',          # Django admin
        r'^/api/auth/',       # Autentikacijske rute
        r'^/static/',         # Statički fajlovi
        r'^/media/',          # Korisnički uploadani fajlovi
        r'^/$',               # Početna stranica
        r'^/favicon.ico$',    # Favicon
    ]
    
    def __init__(self, get_response):
        """Inicijalizira middleware s funkcijom get_response."""
        self.get_response = get_response
    
    def __call__(self, request):
        """
        Obrađuje zahtjev i provjerava token ako je potrebno.
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            HttpResponse: Odgovor na zahtjev
        """
        # Provjeri je li zahtjev upućen API-ju
        if self._is_api_request(request) and not self._is_exempt_path(request.path):
            # Provjeri token
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            
            if not auth_header:
                logger.warning('API request without Authorization header: %s', request.path)
                return JsonResponse({
                    'error': 'Authorization token is required',
                    'code': 'token_required'
                }, status=401)
            
            try:
                # Parsiranje tokena
                token_type, token = auth_header.split(' ', 1)
                
                if token_type.lower() != 'token' and token_type.lower() != 'bearer':
                    logger.warning('Invalid token type: %s', token_type)
                    return JsonResponse({
                        'error': 'Invalid token type',
                        'code': 'invalid_token_type'
                    }, status=401)
                
                # Provjera tokena
                user = self._get_user_from_token(token, token_type)
                
                if not user:
                    logger.warning('Invalid or expired token: %s', token[:10])
                    return JsonResponse({
                        'error': 'Invalid or expired token',
                        'code': 'invalid_token'
                    }, status=401)
                
                # Postavi korisnika na request
                request.user = user
                
            except (ValueError, IndexError):
                logger.warning('Malformed Authorization header: %s', auth_header)
                return JsonResponse({
                    'error': 'Invalid Authorization header format',
                    'code': 'invalid_header_format'
                }, status=401)
        
        # Nastavi s obradom zahtjeva
        response = self.get_response(request)
        return response
    
    def _is_api_request(self, request):
        """
        Provjerava je li zahtjev upućen API rutama.
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            bool: True ako je zahtjev za API, False inače
        """
        return request.path.startswith('/api/')
    
    def _is_exempt_path(self, path):
        """
        Provjerava je li putanja izuzeta od provjere tokena.
        
        Args:
            path: Putanja zahtjeva
            
        Returns:
            bool: True ako je putanja izuzeta, False inače
        """
        return any(re.match(pattern, path) for pattern in self.EXEMPT_PATHS)
    
    def _get_user_from_token(self, token, token_type):
        """
        Dohvaća korisnika na temelju tokena.
        
        Args:
            token: Token za provjeru
            token_type: Tip tokena (token ili bearer)
            
        Returns:
            User: Korisnik ako je token valjan, None inače
        """
        if token_type.lower() == 'token':
            # DRF Token autentikacija
            try:
                token_obj = Token.objects.select_related('user').get(key=token)
                return token_obj.user
            except Token.DoesNotExist:
                return None
        
        elif token_type.lower() == 'bearer':
            # JWT Token autentikacija
            try:
                # Dekodiraj JWT token
                payload = jwt_decode(
                    token, 
                    settings.SECRET_KEY, 
                    algorithms=['HS256']
                )
                
                # Dohvati korisnika iz tokena
                user_id = payload.get('user_id')
                if not user_id:
                    return None
                
                return User.objects.get(id=user_id)
                
            except (InvalidTokenError, ExpiredSignatureError, User.DoesNotExist):
                return None
        
        return None


class WebSocketTokenAuthMiddleware(BaseMiddleware):
    """
    Middleware za autentikaciju WebSocket konekcija.
    
    Ovaj middleware provjerava autentikacijski token u WebSocket
    zahtjevima i postavlja korisnika u scope ako je token valjan.
    """
    
    async def __call__(self, scope, receive, send):
        """
        Obrađuje WebSocket zahtjev i provjerava token.
        
        Args:
            scope: WebSocket scope
            receive: Funkcija za primanje poruka
            send: Funkcija za slanje poruka
            
        Returns:
            Awaitable: Rezultat obrade zahtjeva
        """
        # Izvuci token iz query parametra ili zaglavlja
        query_string = scope.get('query_string', b'').decode()
        query_params = dict(item.split('=') for item in query_string.split('&') if item)
        
        token = query_params.get('token', None)
        
        if not token:
            # Provjeri token u zaglavlju
            headers = dict(scope.get('headers', []))
            auth_header = headers.get(b'authorization', b'').decode()
            
            if auth_header:
                try:
                    token_type, token = auth_header.split(' ', 1)
                except ValueError:
                    token = None
        
        # Ako token postoji, provjeri ga
        if token:
            user = await self._get_user_from_token(token)
            if user:
                scope['user'] = user
            else:
                scope['user'] = AnonymousUser()
        else:
            scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)
    
    @database_sync_to_async
    def _get_user_from_token(self, token):
        """
        Dohvaća korisnika na temelju tokena.
        
        Args:
            token: Token za provjeru
            
        Returns:
            User: Korisnik ako je token valjan, AnonymousUser inače
        """
        # Prvo provjeri kao DRF token
        try:
            token_obj = Token.objects.select_related('user').get(key=token)
            return token_obj.user
        except Token.DoesNotExist:
            pass
        
        # Zatim provjeri kao JWT token
        try:
            # Dekodiraj JWT token
            payload = jwt_decode(
                token, 
                settings.SECRET_KEY, 
                algorithms=['HS256']
            )
            
            # Dohvati korisnika iz tokena
            user_id = payload.get('user_id')
            if not user_id:
                return AnonymousUser()
            
            return User.objects.get(id=user_id)
            
        except (InvalidTokenError, ExpiredSignatureError, User.DoesNotExist):
            return AnonymousUser()


# Helper za upotrebu u routing.py
def TokenAuthMiddlewareStack(inner):
    """
    Kreira Channels middleware stack s autentikacijom.
    
    Args:
        inner: Middleware koji se wrappa
        
    Returns:
        MiddlewareStack: Authentication middleware stack
    """
    return WebSocketTokenAuthMiddleware(AuthMiddlewareStack(inner))