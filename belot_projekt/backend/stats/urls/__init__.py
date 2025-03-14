"""
Inicijalizacijska datoteka za stats URL konfiguraciju.

Ovaj modul inicijalizira osnovne URL rute za aplikaciju statistike.
"""

from django.urls import include, path

from .api import urlpatterns as api_urls
from .web import urlpatterns as web_urls

urlpatterns = [
    path('api/', include((api_urls, 'stats'), namespace='api')),
    path('', include((web_urls, 'stats'), namespace='web')),
] 