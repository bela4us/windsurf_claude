"""
WebSocket routing konfiguracija za Django aplikaciju "lobby".

Ovaj modul definira WebSocket rute koje omogućuju stvarno-vremensku
komunikaciju između servera i klijenata u predvorju Belot igre. WebSocket
veze su potrebne za chat, obavijesti i ažuriranja stanja sobe.
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    # Opća WebSocket veza za predvorje
    # Ova ruta koristi se za općenite obavijesti, pozivnice i ažuriranja
    re_path(r'ws/lobby/$', consumers.LobbyConsumer.as_asgi()),
    
    # WebSocket veza za specifičnu sobu
    # Ova ruta koristi se za chat i ažuriranja specifična za sobu
    re_path(r'ws/lobby/room/(?P<room_id>[0-9a-f-]+)/$', consumers.RoomConsumer.as_asgi()),
]