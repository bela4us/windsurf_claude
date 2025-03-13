"""
WebSocket middleware za autentifikaciju.

Ovaj modul implementira middleware koji osigurava da samo
autentificirani korisnici mogu koristiti WebSocket veze za
komunikaciju s poslužiteljem.
"""

import logging
from urllib.parse import parse_qs
from channels.auth import AuthMiddlewareStack
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.db import close_old_connections
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger('belot.middleware')

@database_sync_to_async
def get_user(token_key):
    """
    Dohvaća korisnika na temelju API tokena.
    
    Args:
        token_key: Ključ autentikacijskog tokena
        
    Returns:
        User: Korisnički objekt ako je token valjan, inače AnonymousUser
    """
    try:
        token = Token.objects.get(key=token_key)
        return token.user
    except Token.DoesNotExist:
        return AnonymousUser()
    except Exception as e:
        logger.error(f"Greška pri dohvaćanju tokena: {str(e)}")
        return AnonymousUser()

class WebSocketJWTAuthMiddleware(BaseMiddleware):
    """
    Middleware za autentifikaciju WebSocket veza putem JWT tokena.
    
    Provjerava autentikacijski token u URL parametrima ili
    u kolačićima sesije kako bi autentificirao WebSocket vezu.
    """
    
    def __init__(self, inner):
        """Inicijalizira middleware s inner aplikacijom."""
        super().__init__(inner)
    
    async def __call__(self, scope, receive, send):
        """
        Asinkrona metoda koja se poziva za svaku WebSocket vezu.
        
        Provjerava autentikaciju i ažurira scope s korisničkim podacima.
        """
        # Zatvaranje starih veza s bazom podataka
        close_old_connections()
        
        # Izvlačenje tokena iz parametara upita
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        
        token = None
        
        # Provjera tokena u parametrima
        if 'token' in query_params:
            token = query_params['token'][0]
        # Provjera tokena u zaglavlju
        elif 'authorization' in scope.get('headers', []):
            auth_header = dict(scope['headers']).get(b'authorization', b'').decode()
            if auth_header.startswith('Token '):
                token = auth_header.split(' ')[1]
        
        # Dohvaćanje korisnika na temelju tokena
        if token:
            scope['user'] = await get_user(token)
        else:
            scope['user'] = AnonymousUser()
        
        # Proslijeđivanje na sljedeći middleware ili aplikaciju
        return await super().__call__(scope, receive, send)

def WebSocketAuthMiddlewareStack(inner):
    """
    Vraća WebSocket middleware stack s autentikacijom.
    
    Args:
        inner: Inner aplikacija za middleware stack
        
    Returns:
        Channels middleware stack s autentifikacijom
    """
    return WebSocketJWTAuthMiddleware(AuthMiddlewareStack(inner))