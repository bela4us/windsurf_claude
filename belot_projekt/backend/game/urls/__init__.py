"""
Inicijalizacijska datoteka za URL konfiguracije.
"""
from django.urls import path, include

urlpatterns = [
    path('api/', include('game.urls.api')),
    path('', include('game.urls.web')),
]