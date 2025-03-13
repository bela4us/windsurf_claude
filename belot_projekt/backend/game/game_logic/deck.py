"""
Modul koji definira klasu špila za Belot igru.

Ovaj modul pruža implementaciju klase Deck koja predstavlja špil karata
u igri Belot, s metodama za miješanje, dijeljenje i vučenje karata.
"""

import random
from game.game_logic.card import Card


class Deck:
    """
    Klasa koja predstavlja špil karata u igri Belot.
    
    Špil se sastoji od 32 karte - 8 vrijednosti (7, 8, 9, 10, J, Q, K, A)
    u 4 boje (S, H, D, C).
    """
    
    def __init__(self):
        """
        Inicijalizira standardni špil karata za Belot.
        
        Špil sadrži 32 karte - 8 vrijednosti u 4 boje.
        """
        self.cards = []
        
        # Stvaranje svih 32 karte
        for suit in Card.VALID_SUITS:
            for value in Card.VALID_VALUES:
                self.cards.append(Card(value, suit))
    
    def shuffle(self):
        """
        Miješa špil karata.
        
        Returns:
            Deck: Instanca špila za ulančavanje metoda
        """
        random.shuffle(self.cards)
        return self
    
    def draw(self):
        """
        Vuče kartu s vrha špila.
        
        Returns:
            Card: Karta s vrha špila
            
        Raises:
            ValueError: Ako je špil prazan
        """
        if not self.cards:
            raise ValueError("Špil je prazan!")
        
        return self.cards.pop()
    
    def deal(self, num_players, cards_per_player):
        """
        Dijeli karte iz špila određenom broju igrača.
        
        Args:
            num_players: Broj igrača kojima se dijele karte
            cards_per_player: Broj karata po igraču
            
        Returns:
            list: Lista ruku igrača, gdje je svaka ruka lista karata
            
        Raises:
            ValueError: Ako nema dovoljno karata u špilu za dijeljenje
        """
        total_cards_needed = num_players * cards_per_player
        if len(self.cards) < total_cards_needed:
            raise ValueError(
                f"Nema dovoljno karata u špilu za dijeljenje! "
                f"Potrebno: {total_cards_needed}, Dostupno: {len(self.cards)}"
            )
        
        # Stvaranje ruku igrača
        hands = [[] for _ in range(num_players)]
        
        # Dijeljenje karata po redu svakom igraču
        for _ in range(cards_per_player):
            for i in range(num_players):
                hands[i].append(self.draw())
        
        return hands
    
    def __len__(self):
        """
        Vraća broj karata u špilu.
        
        Returns:
            int: Broj karata u špilu
        """
        return len(self.cards)
    
    def __str__(self):
        """
        Vraća string reprezentaciju špila.
        
        Returns:
            str: String s informacijama o špilu
        """
        return f"Deck with {len(self.cards)} cards"
    
    def __repr__(self):
        """
        Vraća reprezentaciju špila za debagiranje.
        
        Returns:
            str: String s detaljnim informacijama o špilu
        """
        return f"Deck(cards={self.cards})"