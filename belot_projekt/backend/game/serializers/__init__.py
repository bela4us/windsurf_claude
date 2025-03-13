"""
Inicijalizacijski modul za paket serializatora u Belot igri.

Serializatori su odgovorni za pretvaranje složenih tipova podataka kao što su Django
queryset-ovi i model instance u Python izvorne tipove podataka koji se mogu lako
pretvoriti u JSON ili druge formate sadržaja. Također omogućuju deserializaciju,
pretvarajući parsirane podatke nazad u složene tipove.

U kontekstu Belot igre, serializatori se koriste za:
- Izlaganje podataka o igri kroz REST API
- Slanje podataka kroz WebSocket kanale
- Validaciju ulaznih podataka od klijenata
"""

from game.serializers.game_serializers import (
    GameSerializer,
    GameCreateSerializer,
    GameDetailSerializer,
    GameListSerializer,
    GameStateSerializer
)

from game.serializers.move_serializers import (
    MoveSerializer,
    MoveCreateSerializer,
    MoveListSerializer,
    DeclarationSerializer,
    DeclarationCreateSerializer,
    RoundSerializer,
    RoundDetailSerializer
)

# Definiranje javnog API-ja ovog modula
__all__ = [
    # Game serializatori
    'GameSerializer',
    'GameCreateSerializer',
    'GameDetailSerializer',
    'GameListSerializer',
    'GameStateSerializer',
    
    # Move serializatori
    'MoveSerializer',
    'MoveCreateSerializer',
    'MoveListSerializer',
    
    # Declaration serializatori
    'DeclarationSerializer',
    'DeclarationCreateSerializer',
    
    # Round serializatori
    'RoundSerializer',
    'RoundDetailSerializer',
]