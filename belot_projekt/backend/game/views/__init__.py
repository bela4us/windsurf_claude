"""
Inicijalizacijski modul za paket pogleda (views) u Belot igri.

Pogledi su komponente koje upravljaju prezentacijskim slojem aplikacije,
odgovaraju na HTTP zahtjeve i odgovore, i komuniciraju s korisnicima. Ovaj
paket sadrži dvije glavne vrste pogleda:

1. Web pogledi (game_views.py) - klasični Django pogledi koji vraćaju
   HTML stranice za web korisničko sučelje

2. API pogledi (api_views.py) - Django REST Framework pogledi koji vraćaju
   JSON podatke za front-end aplikaciju i mobilne klijente

Pogledi koriste servisni sloj za izvršavanje poslovne logike i repozitorije
za pristup podacima, čime se održava čista arhitektura i odvajanje odgovornosti.
"""

from game.views.game_views import (
    GameListView,
    GameDetailView,
    GameCreateView,
    GameJoinView,
    LobbyView,
    GamePlayView
)

from game.views.api_views import (
    GameViewSet,
    RoundViewSet,
    MoveViewSet,
    DeclarationViewSet,
    GameActionView,
    GameStatisticsView,
    CurrentGamesView
)

# Definiranje javnog API-ja ovog modula
__all__ = [
    # Web pogledi
    'GameListView',
    'GameDetailView',
    'GameCreateView',
    'GameJoinView',
    'LobbyView',
    'GamePlayView',
    
    # API pogledi
    'GameViewSet',
    'RoundViewSet',
    'MoveViewSet',
    'DeclarationViewSet',
    'GameActionView',
    'GameStatisticsView',
    'CurrentGamesView'
]