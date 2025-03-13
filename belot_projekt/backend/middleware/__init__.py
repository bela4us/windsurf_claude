"""
Inicijalizacijski modul za middleware komponente Belot aplikacije.

Middleware komponente omogućuju procesiranje zahtjeva prije nego što dođu do view-ova,
ili procesiranje odgovora nakon što ih view-ovi obrade. Korisni su za implementaciju
funkcionalnosti koje trebaju djelovati na više ili sve zahtjeve, poput autentikacije,
logiranja, limitiranja broja zahtjeva i slično.
"""

from .auth_middleware import TokenAuthMiddleware, WebSocketTokenAuthMiddleware, TokenAuthMiddlewareStack
from .rate_limiter import RateLimiterMiddleware, APIThrottleMiddleware
from .request_logger import RequestLoggerMiddleware, QueryCountMiddleware
from .cors_middleware import CORSMiddleware, SameSiteMiddleware

__all__ = [
    # Autentikacija
    'TokenAuthMiddleware',
    'WebSocketTokenAuthMiddleware',
    'TokenAuthMiddlewareStack',
    
    # Ograničavanje broja zahtjeva
    'RateLimiterMiddleware',
    'APIThrottleMiddleware',
    
    # Logiranje i praćenje
    'RequestLoggerMiddleware',
    'QueryCountMiddleware',
    
    # CORS i kolačići
    'CORSMiddleware',
    'SameSiteMiddleware',
]