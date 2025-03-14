"""
Inicijalizacijski modul za URL konfiguracije "users" aplikacije.

Ovaj modul omogućuje jednostavan import URL konfiguracija iz drugih modula.
"""

from .web import urlpatterns as web_urlpatterns
from .api import urlpatterns as api_urlpatterns

__all__ = ['web_urlpatterns', 'api_urlpatterns'] 