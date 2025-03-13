"""
Konfiguracija WebSocket ruta za Belot igru.

Ovaj modul definira WebSocket rute koje povezuju URL putanje s
odgovarajućim WebSocket potrošačima (consumers). Konfiguracija je
neophodna za real-time komunikaciju u Belot igri, omogućujući igračima
da vide poteze drugih igrača, prime obavijesti o stanju igre, i komuniciraju
putem chata.
"""

from django.urls import re_path

from game.consumers import GameConsumer

# Definicija WebSocket URL obrazaca
# Ovi obrasci se koriste u asgi.py datoteci za usmjeravanje WebSocket zahtjeva
websocket_urlpatterns = [
    # Ruta za predvorje (lobby) igre - privremeno komentirano dok se LobbyConsumer ne implementira
    # re_path(r'^ws/lobby/$', LobbyConsumer.as_asgi()),
    
    # Ruta za pojedinačnu igru s room_code parametrom u URL-u
    # Primjer URL-a: ws://domena/ws/game/ABC123/ gdje je ABC123 kod sobe
    re_path(r'ws/game/(?P<room_code>\w+)/$', GameConsumer.as_asgi()),
    
    # Ruta za pristup igri prema ID-u
    # Primjer URL-a: ws://domena/ws/game/id/550e8400-e29b-41d4-a716-446655440000/
    # Koristan za scenarije gdje znamo UUID igre
    re_path(r'ws/game/id/(?P<game_id>[\w-]+)/$', GameConsumer.as_asgi()),
]