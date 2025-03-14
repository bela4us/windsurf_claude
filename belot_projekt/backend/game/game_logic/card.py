"""
Modul koji definira osnovnu klasu karte za Belot igru.

Ovaj modul pruža implementaciju klase Card koja predstavlja jednu kartu u
igri Belot, s metodama za rukovanje i usporedbu karata.
"""
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

class Card:
    """
    Klasa koja predstavlja jednu kartu u igri Belot.
    
    Karta ima vrijednost (7, 8, 9, 10, J, Q, K, A) i boju (S, H, D, C).
    """
    
    # Dozvoljene vrijednosti i boje karata
    VALID_VALUES = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    VALID_SUITS = ['S', 'H', 'D', 'C']
    
    # Redoslijed vrijednosti karata za usporedbu
    RANKS = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    
    # Mapiranje kodova boja na njihova puna imena
    SUIT_NAMES = {
        'S': 'Spades',
        'H': 'Hearts',
        'D': 'Diamonds',
        'C': 'Clubs'
    }
    
    # Mapiranje kodova vrijednosti na njihova puna imena
    VALUE_NAMES = {
        'A': 'Ace',
        'K': 'King',
        'Q': 'Queen',
        'J': 'Jack',
        '10': 'Ten',
        '9': 'Nine',
        '8': 'Eight',
        '7': 'Seven'
    }
    
    # Bodovne vrijednosti kada boja nije adut
    NON_TRUMP_VALUES = {
        'A': 11, '10': 10, 'K': 4, 'Q': 3, 'J': 2, '9': 0, '8': 0, '7': 0
    }
    
    # Bodovne vrijednosti kada je boja adut
    TRUMP_VALUES = {
        'J': 20, '9': 14, 'A': 11, '10': 10, 'K': 4, 'Q': 3, '8': 0, '7': 0
    }
    
    # Keširanje instanci karata
    _card_instances = {}
    
    def __init__(self, value, suit):
        """
        Inicijalizira kartu s vrijednošću i bojom.
        
        Args:
            value: Vrijednost karte ('7', '8', '9', '10', 'J', 'Q', 'K', 'A')
            suit: Boja karte ('S', 'H', 'D', 'C')
            
        Raises:
            ValueError: Ako je vrijednost ili boja nevažeća
        """
        if value not in self.VALID_VALUES:
            raise ValueError(f"Nevažeća vrijednost karte: {value}")
        if suit not in self.VALID_SUITS:
            raise ValueError(f"Nevažeća boja karte: {suit}")
        
        self.value = value
        self.suit = suit
        self.code = value + suit  # Npr. "AS" za asa pik
        self.rank = value  # Dodajemo atribut rank koji verificator očekuje
    
    @lru_cache(maxsize=128)
    def get_value(self, trump_suit=None):
        """
        Vraća bodovnu vrijednost karte ovisno je li adut ili ne.
        
        Args:
            trump_suit: Adutska boja (ako je None, karta se tretira kao ne-adut)
            
        Returns:
            int: Bodovna vrijednost karte
        """
        try:
            # Ako je adut definiran i karta je adut
            if trump_suit and self.suit == self._normalize_suit(trump_suit):
                return self.TRUMP_VALUES.get(self.value, 0)
            else:
                return self.NON_TRUMP_VALUES.get(self.value, 0)
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju vrijednosti karte {self.code}: {e}", exc_info=True)
            return 0
    
    @staticmethod
    @lru_cache(maxsize=32)
    def _normalize_suit(suit):
        """
        Pretvara puno ime boje u kod boje.
        
        Args:
            suit: Boja (puno ime ili kod)
            
        Returns:
            str: Kod boje ('S', 'H', 'D', 'C')
        """
        # Mapiranje punih imena boja na kodove
        suit_map = {
            'spades': 'S',
            'hearts': 'H',
            'diamonds': 'D',
            'clubs': 'C'
        }
        
        # Ako je već kod, vrati ga
        if suit in Card.VALID_SUITS:
            return suit
        
        # Inače pokušaj mapirati iz punog imena
        return suit_map.get(suit.lower() if isinstance(suit, str) else '', suit)
    
    @classmethod
    def from_code(cls, code):
        """
        Stvara novu kartu iz koda karte. Koristi keširanje za poboljšanje performansi.
        
        Args:
            code: Kod karte (npr. "AS" za asa pik)
            
        Returns:
            Card: Nova instanca karte
            
        Raises:
            ValueError: Ako je kod nevažeći
        """
        try:
            # Provjeri je li karta već u kešu
            if code in cls._card_instances:
                return cls._card_instances[code]
            
            if not cls.is_valid_code(code):
                raise ValueError(f"Nevažeći kod karte: {code}")
            
            # Posljednji znak je uvijek boja
            suit = code[-1]
            
            # Sve prije posljednjeg znaka je vrijednost
            value = code[:-1]
            
            # Stvori novu kartu i spremi je u keš
            card = cls(value, suit)
            cls._card_instances[code] = card
            return card
        except Exception as e:
            logger.error(f"Greška pri stvaranju karte iz koda {code}: {e}", exc_info=True)
            raise ValueError(f"Nevažeći kod karte: {code}")
    
    @classmethod
    @lru_cache(maxsize=128)
    def is_valid_code(cls, code):
        """
        Provjerava je li kod karte valjan.
        
        Args:
            code: Kod karte za provjeru
            
        Returns:
            bool: True ako je kod valjan, False inače
        """
        try:
            if not code or not isinstance(code, str) or len(code) < 2:
                return False
            
            # Posljednji znak je boja
            suit = code[-1]
            if suit not in cls.VALID_SUITS:
                return False
            
            # Sve prije posljednjeg znaka je vrijednost
            value = code[:-1]
            if value not in cls.VALID_VALUES:
                return False
            
            return True
        except Exception as e:
            logger.error(f"Greška pri provjeri valjanosti koda karte {code}: {e}", exc_info=True)
            return False
    
    @classmethod
    @lru_cache(maxsize=8)
    def get_suit_name(cls, suit):
        """
        Vraća puno ime boje iz koda boje.
        
        Args:
            suit: Kod boje ('S', 'H', 'D', 'C')
            
        Returns:
            str: Puno ime boje ili "Unknown" ako boja nije poznata
        """
        return cls.SUIT_NAMES.get(suit, "Unknown")
    
    @classmethod
    @lru_cache(maxsize=16)
    def get_value_name(cls, value):
        """
        Vraća puno ime vrijednosti iz koda vrijednosti.
        
        Args:
            value: Kod vrijednosti ('7', '8', '9', '10', 'J', 'Q', 'K', 'A')
            
        Returns:
            str: Puno ime vrijednosti ili "Unknown" ako vrijednost nije poznata
        """
        return cls.VALUE_NAMES.get(value, "Unknown")
    
    def get_rank_index(self):
        """
        Vraća indeks ranga karte u redoslijedu vrijednosti.
        
        Returns:
            int: Indeks ranga karte (0-7)
        """
        try:
            return self.RANKS.index(self.value)
        except ValueError:
            logger.error(f"Nevažeći rang karte: {self.value}")
            return -1
    
    def get_code(self):
        """
        Vraća kod karte.
        
        Returns:
            str: Kod karte (npr. "AS" za asa pik)
        """
        return self.code
    
    def is_trump(self, trump_suit):
        """
        Provjerava je li karta adut.
        
        Args:
            trump_suit: Adutska boja
            
        Returns:
            bool: True ako je karta adut, False inače
        """
        if not trump_suit:
            return False
            
        normalized_trump = self._normalize_suit(trump_suit)
        return self.suit == normalized_trump
    
    @classmethod
    def create_deck(cls):
        """
        Stvara novi špil od 32 karte za Belot.
        
        Returns:
            list: Lista od 32 karte
        """
        deck = []
        for value in cls.VALID_VALUES:
            for suit in cls.VALID_SUITS:
                deck.append(cls(value, suit))
        return deck
    
    def __eq__(self, other):
        """
        Uspoređuje dvije karte na jednakost.
        
        Dvije karte su jednake ako imaju istu vrijednost i boju.
        
        Args:
            other: Druga karta za usporedbu
            
        Returns:
            bool: True ako su karte jednake, False inače
        """
        if not isinstance(other, Card):
            # Ako je other string, pokušaj ga pretvoriti u kartu
            if isinstance(other, str):
                try:
                    other = Card.from_code(other)
                except ValueError:
                    return False
            else:
                return False
                
        return self.value == other.value and self.suit == other.suit
    
    def __lt__(self, other):
        """
        Uspoređuje je li ova karta manja od druge karte.
        
        Usporedba se vrši prema redoslijedu vrijednosti karata.
        
        Args:
            other: Druga karta za usporedbu
            
        Returns:
            bool: True ako je ova karta manja od druge, False inače
        """
        if not isinstance(other, Card):
            return NotImplemented
        
        # Podrazumijevamo ne-adutsku usporedbu (za jednostavnost)
        return self.get_rank_index() < other.get_rank_index()
    
    def __gt__(self, other):
        """
        Uspoređuje je li ova karta veća od druge karte.
        
        Usporedba se vrši prema redoslijedu vrijednosti karata.
        
        Args:
            other: Druga karta za usporedbu
            
        Returns:
            bool: True ako je ova karta veća od druge, False inače
        """
        if not isinstance(other, Card):
            return NotImplemented
        
        # Podrazumijevamo ne-adutsku usporedbu (za jednostavnost)
        return self.get_rank_index() > other.get_rank_index()
    
    def __hash__(self):
        """
        Vraća hash vrijednost karte.
        
        Ovo omogućuje korištenje karata kao ključeva u rječnicima i elementima setova.
        
        Returns:
            int: Hash vrijednost karte
        """
        return hash((self.value, self.suit))
    
    def __str__(self):
        """
        Vraća string reprezentaciju karte.
        
        Returns:
            str: String u formatu "vrijednost of boja" (npr. "Ace of Spades")
        """
        return f"{self.get_value_name(self.value)} of {self.get_suit_name(self.suit)}"
    
    def __repr__(self):
        """
        Vraća reprezentaciju karte za programere.
        
        Returns:
            str: String u formatu "Card('vrijednost', 'boja')"
        """
        return f"Card('{self.value}', '{self.suit}')"