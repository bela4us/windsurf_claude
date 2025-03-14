"""
Modul koji definira klasu špila za Belot igru.

Ovaj modul pruža implementaciju klase Deck koja predstavlja špil karata
u igri Belot, s metodama za miješanje, dijeljenje i vučenje karata.
"""

import random
import logging
from functools import lru_cache
from game.game_logic.card import Card
from utils.decorators import track_execution_time

# Konfiguracija loggera
logger = logging.getLogger(__name__)

class Deck:
    """
    Klasa koja predstavlja špil karata u igri Belot.
    
    Špil se sastoji od 32 karte - 8 vrijednosti (7, 8, 9, 10, J, Q, K, A)
    u 4 boje (S, H, D, C).
    
    Attributes:
        cards (list): Lista karata u špilu
        _original_order (list): Originalni redoslijed karata prije miješanja (za testiranje)
    """
    
    # Konstante za Belot
    NUM_CARDS = 32
    VALID_PLAYERS = [2, 3, 4]  # Validni brojevi igrača
    
    # Načini dijeljenja za Belot (3-2-3 ili drugi načini)
    DEALING_PATTERNS = {
        "standard": [3, 2, 3],  # Standardni način dijeljenja: 3 karte, pa 2, pa 3
        "equal": [4, 4],         # Jednako dijeljenje: 4 karte, pa još 4
        "gradual": [1, 2, 3, 2]  # Postupno: 1 karta, pa 2, pa 3, pa 2
    }
    
    @track_execution_time
    def __init__(self, use_cached_cards=True):
        """
        Inicijalizira standardni špil karata za Belot.
        
        Špil sadrži 32 karte - 8 vrijednosti u 4 boje.
        
        Args:
            use_cached_cards (bool): Koristi keširane instance karata za bolju performansu
        """
        self.cards = []
        self._original_order = []
        
        try:
            # Stvaranje svih 32 karte
            if use_cached_cards:
                self.cards = self._create_deck_cached()
            else:
                self.cards = self._create_deck_standard()
                
            # Spremi originalnu listu (za testiranje i verifikaciju)
            self._original_order = self.cards.copy()
            
            logger.debug(f"Stvoren novi špil s {len(self.cards)} karata")
            
        except Exception as e:
            logger.error(f"Greška pri stvaranju špila: {str(e)}", exc_info=True)
            raise
    
    @classmethod
    @lru_cache(maxsize=1)  # Keširaj rezultat - uvijek je isti
    def _create_deck_cached(cls):
        """
        Stvara listu karata za špil koristeći keširane instance karata.
        
        Returns:
            list: Lista od 32 karte za Belot
        """
        deck = []
        for suit in Card.VALID_SUITS:
            for value in Card.VALID_VALUES:
                deck.append(Card.from_code(f"{value}{suit}"))
        return deck
    
    @classmethod
    def _create_deck_standard(cls):
        """
        Stvara listu karata za špil standardnim načinom.
        
        Returns:
            list: Lista od 32 karte za Belot
        """
        deck = []
        for suit in Card.VALID_SUITS:
            for value in Card.VALID_VALUES:
                deck.append(Card(value, suit))
        return deck
    
    @track_execution_time
    def shuffle(self):
        """
        Miješa špil karata.
        
        Returns:
            Deck: Instanca špila za ulančavanje metoda
        """
        try:
            random.shuffle(self.cards)
            logger.debug("Špil uspješno promiješan")
            return self
        except Exception as e:
            logger.error(f"Greška pri miješanju špila: {str(e)}", exc_info=True)
            raise
    
    @track_execution_time
    def draw(self):
        """
        Vuče kartu s vrha špila.
        
        Returns:
            Card: Karta s vrha špila
            
        Raises:
            ValueError: Ako je špil prazan
        """
        if not self.cards:
            error_msg = "Špil je prazan!"
            logger.warning(error_msg)
            raise ValueError(error_msg)
        
        try:
            card = self.cards.pop()
            logger.debug(f"Izvučena karta: {card}")
            return card
        except Exception as e:
            logger.error(f"Greška pri izvlačenju karte: {str(e)}", exc_info=True)
            raise
    
    @track_execution_time
    def deal(self, num_players, cards_per_player=None, pattern=None):
        """
        Dijeli karte iz špila određenom broju igrača.
        
        Args:
            num_players (int): Broj igrača kojima se dijele karte
            cards_per_player (int, optional): Broj karata po igraču (ili None za automatsko određivanje)
            pattern (str or list, optional): Obrazac dijeljenja (npr. "standard", "equal") ili lista brojeva
            
        Returns:
            list: Lista ruku igrača, gdje je svaka ruka lista karata
            
        Raises:
            ValueError: Ako nema dovoljno karata u špilu za dijeljenje ili ako su parametri nevažeći
        """
        # Provjera broja igrača
        if num_players not in self.VALID_PLAYERS:
            error_msg = f"Nevažeći broj igrača: {num_players}. Dozvoljeni brojevi: {self.VALID_PLAYERS}"
            logger.warning(error_msg)
            raise ValueError(error_msg)
        
        # Određivanje broja karata po igraču
        if cards_per_player is None:
            cards_per_player = self.NUM_CARDS // num_players
        
        # Provjera ima li dovoljno karata
        total_cards_needed = num_players * cards_per_player
        if len(self.cards) < total_cards_needed:
            error_msg = (
                f"Nema dovoljno karata u špilu za dijeljenje! "
                f"Potrebno: {total_cards_needed}, Dostupno: {len(self.cards)}"
            )
            logger.warning(error_msg)
            raise ValueError(error_msg)
        
        # Stvaranje ruku igrača
        hands = [[] for _ in range(num_players)]
        
        try:
            # Ako je naveden obrazac, koristi ga za dijeljenje
            if pattern:
                self._deal_with_pattern(hands, pattern)
            else:
                # Inače, standardno dijeljenje
                for _ in range(cards_per_player):
                    for i in range(num_players):
                        hands[i].append(self.draw())
            
            logger.debug(f"Karte uspješno podijeljene za {num_players} igrača")
            return hands
        except Exception as e:
            logger.error(f"Greška pri dijeljenju karata: {str(e)}", exc_info=True)
            raise
    
    def _deal_with_pattern(self, hands, pattern):
        """
        Dijeli karte prema zadanom obrascu.
        
        Args:
            hands (list): Lista ruku igrača
            pattern (str or list): Obrazac dijeljenja
            
        Raises:
            ValueError: Ako je obrazac nevažeći
        """
        # Ako je pattern string, dohvati odgovarajući obrazac iz konstanti
        if isinstance(pattern, str):
            if pattern not in self.DEALING_PATTERNS:
                raise ValueError(f"Nepoznati obrazac dijeljenja: {pattern}")
            pattern = self.DEALING_PATTERNS[pattern]
        
        # Dijeljenje prema obrascu
        for num_cards in pattern:
            for i in range(len(hands)):
                for _ in range(num_cards):
                    hands[i].append(self.draw())
    
    @track_execution_time
    def return_cards(self, cards):
        """
        Vraća karte u špil.
        
        Args:
            cards (list): Lista karata koje se vraćaju u špil
            
        Returns:
            Deck: Instanca špila za ulančavanje metoda
        """
        try:
            self.cards.extend(cards)
            logger.debug(f"Vraćeno {len(cards)} karata u špil")
            return self
        except Exception as e:
            logger.error(f"Greška pri vraćanju karata u špil: {str(e)}", exc_info=True)
            raise
    
    def reset(self):
        """
        Vraća špil u početno stanje (sve karte, nepromiješane).
        
        Returns:
            Deck: Instanca špila za ulančavanje metoda
        """
        try:
            self.cards = self._original_order.copy()
            logger.debug("Špil vraćen u početno stanje")
            return self
        except Exception as e:
            logger.error(f"Greška pri resetiranju špila: {str(e)}", exc_info=True)
            raise
    
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
        return f"Špil s {len(self.cards)} karata"
    
    def __repr__(self):
        """
        Vraća reprezentaciju špila za debagiranje.
        
        Returns:
            str: String s detaljnim informacijama o špilu
        """
        return f"Deck(cards=[{', '.join(repr(card) for card in self.cards[:3])}...])"