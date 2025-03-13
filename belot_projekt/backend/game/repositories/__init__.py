"""
Inicijalizacijski modul za repozitorijski sloj Belot igre.

Repozitorijski sloj implementira uzorak Repository Pattern koji služi kao
apstrakcija za pristup modelima podataka. Ovaj sloj odvaja poslovnu logiku
od direktnog pristupa bazi podataka, omogućujući lakše testiranje i održavanje.

Repozitoriji u ovom modulu pružaju metode za dohvaćanje, stvaranje, ažuriranje
i brisanje entiteta igre (igre, runde, potezi, zvanja), kao i za izvršavanje
složenijih upita koji objedinjuju više modela.
"""

# Uvoz repozitorija za lakši pristup iz drugih modula
from game.repositories.game_repository import GameRepository
from game.repositories.move_repository import MoveRepository

# Definiranje javnog API-ja ovog modula
__all__ = [
    'GameRepository',
    'MoveRepository'
]