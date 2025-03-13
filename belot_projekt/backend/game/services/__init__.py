"""
Inicijalizacijski modul za servisni sloj Belot igre.

Servisni sloj sadrži poslovnu logiku aplikacije, implementiranu kao skup
servisnih klasa koje upravljaju složenim operacijama i pravilima igre.
Servisne klase koriste repozitorije za pristup podacima i nude više razine
apstrakcije za kontrolere i potrošače.

Ovaj modul omogućuje jednostavan uvoz servisnih klasa iz drugih dijelova
aplikacije i definira njihov javni API.
"""

# Uvoz servisnih klasa za lakši pristup iz drugih modula
from game.services.game_service import GameService
from game.services.scoring_service import ScoringService

# Definiranje javnog API-ja ovog modula
__all__ = [
    'GameService',
    'ScoringService'
]