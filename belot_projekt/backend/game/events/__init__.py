"""
Inicijalizacijski modul za event-driven arhitekturu Belot igre.

Ovaj modul omogućuje jednostavan pristup event sustavu kroz aplikaciju.
Event-driven arhitektura omogućuje labavo povezivanje različitih komponenti
sustava kroz mehanizam pretplate na događaje (observer pattern).

Primjeri upotrebe:
- Obavještavanje igrača kroz WebSockets kada se dogodi promjena u igri
- Osvježavanje stanja igre kada igrač izvrši potez
- Ažuriranje statistike igrača nakon završetka igre
"""

from game.events.events import (
    GameEvent,
    GameCreatedEvent,
    GameJoinedEvent,
    GameStartedEvent,
    GameFinishedEvent,
    RoundStartedEvent,
    RoundFinishedEvent,
    TrumpCalledEvent,
    MovePlayedEvent,
    TrickCompletedEvent,
    DeclarationMadeEvent,
    BelaCalledEvent,
    ChatMessageEvent
)

from game.events.handlers import (
    EventHandler,
    WebSocketEventHandler,
    GameStateUpdateHandler,
    NotificationHandler,
    StatisticsUpdateHandler,
    register_handler,
    unregister_handler,
    dispatch_event
)

# Definiranje javnog API-ja ovog modula
__all__ = [
    # Events
    'GameEvent',
    'GameCreatedEvent',
    'GameJoinedEvent',
    'GameStartedEvent',
    'GameFinishedEvent',
    'RoundStartedEvent',
    'RoundFinishedEvent',
    'TrumpCalledEvent',
    'MovePlayedEvent',
    'TrickCompletedEvent',
    'DeclarationMadeEvent',
    'BelaCalledEvent',
    'ChatMessageEvent',
    
    # Handlers
    'EventHandler',
    'WebSocketEventHandler',
    'GameStateUpdateHandler',
    'NotificationHandler',
    'StatisticsUpdateHandler',
    
    # Functions
    'register_handler',
    'unregister_handler',
    'dispatch_event'
]