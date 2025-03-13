"""
Inicijalizacijski modul za modele podataka Belot igre.

Ovaj modul služi kao središnja točka za uvoz svih modela podataka 
vezanih uz Belot igru. Olakšava pristup modelima tako da se mogu
direktno uvoziti iz glavnog paketa 'game.models' umjesto iz pojedinačnih
datoteka.

Primjer korištenja:
    from game.models import Game, Round, Move
    umjesto:
    from game.models.game import Game
    from game.models.round import Round
    from game.models.move import Move
"""

# Uvoz svih modela za lakši pristup iz drugih modula
from game.models.game import Game
from game.models.round import Round
from game.models.move import Move
from game.models.declaration import Declaration

# Definiranje koje klase čine javno API sučelje ovog paketa
__all__ = [
    'Game',
    'Round',
    'Move',
    'Declaration'
]