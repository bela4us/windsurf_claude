"""
Modul koji definira klasu igrača za Belot igru.

Ovaj modul pruža implementaciju klase Player koja predstavlja jednog igrača
u igri Belot, s metodama za upravljanje kartama, potezima i stanjem igrača.
"""

import logging
from functools import lru_cache
from game.game_logic.card import Card
from utils.decorators import track_execution_time

# Konfiguracija loggera
logger = logging.getLogger(__name__)

class Player:
    """
    Klasa koja predstavlja jednog igrača u igri Belot.
    
    Igrač ima svoje osobne podatke, karte u ruci, tim kojem pripada
    i metode za igranje poteza i upravljanje kartama.
    
    Attributes:
        id (str): Jedinstveni identifikator igrača
        username (str): Korisničko ime igrača
        team (str): Tim kojem igrač pripada ('a' ili 'b', None ako nije dodijeljen)
        hand (list): Karte u ruci igrača
        score (int): Osobna statistika bodova
        games_played (int): Broj odigranih igara
        games_won (int): Broj pobjeda
        is_active (bool): Je li igrač aktivan u igri
        is_ready (bool): Je li igrač spreman za početak igre
        is_dealer (bool): Je li igrač trenutni djelitelj
        _cache_timestamp (float): Vremenska oznaka za invalidaciju keša
    """
    
    # Konstante za timove
    TEAM_A = 'a'
    TEAM_B = 'b'
    
    # Konstante za redoslijed boja i vrijednosti
    SUIT_ORDER = {'S': 0, 'H': 1, 'D': 2, 'C': 3}
    VALUE_ORDER = {'7': 0, '8': 1, '9': 2, '10': 3, 'J': 4, 'Q': 5, 'K': 6, 'A': 7}
    
    @track_execution_time
    def __init__(self, id, username, team=None):
        """
        Inicijalizira novog igrača.
        
        Args:
            id (str): Jedinstveni identifikator igrača
            username (str): Korisničko ime igrača
            team (str, optional): Tim kojem igrač pripada ('a' ili 'b', None ako nije dodijeljen)
            
        Raises:
            ValueError: Ako je tim nevažeći
        """
        try:
            self.id = id
            self.username = username
            
            # Validacija tima
            if team is not None and team not in [self.TEAM_A, self.TEAM_B]:
                raise ValueError(f"Nevažeći tim: {team}. Dozvoljeni timovi: {self.TEAM_A}, {self.TEAM_B}")
            
            self.team = team
            self.hand = []  # Karte u ruci igrača
            self.score = 0  # Osobna statistika bodova
            self.games_played = 0  # Broj odigranih igara
            self.games_won = 0  # Broj pobjeda
            self.is_active = True  # Je li igrač aktivan u igri
            self.is_ready = False  # Je li igrač spreman za početak igre
            self.is_dealer = False  # Je li igrač trenutni djelitelj
            
            # Privatni atributi za keširanje
            self._cache_timestamp = 0.0
            self._hand_by_suit = {}  # Keširanje karata po bojama
            
            logger.info(f"Stvoren novi igrač: {username} (ID: {id}, tim: {team})")
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri inicijalizaciji igrača: {str(e)}", exc_info=True)
            raise
    
    def _invalidate_cache(self):
        """Invalidira sve kešove povezane s igračem."""
        import time
        self._cache_timestamp = time.time()
        self._hand_by_suit = {}  # Poništi keš karata po bojama
    
    @track_execution_time
    def add_card(self, card):
        """
        Dodaje kartu u ruku igrača.
        
        Args:
            card (Card or str): Karta koja se dodaje (objekt Card ili string)
            
        Returns:
            bool: True ako je karta uspješno dodana, False inače
            
        Raises:
            ValueError: Ako je format karte nevažeći
        """
        try:
            # Pretvori string u objekt Card ako je potrebno
            if isinstance(card, str):
                try:
                    card = Card.from_code(card)
                except ValueError as e:
                    logger.warning(f"Nevažeći kod karte: {card}, {str(e)}")
                    raise ValueError(f"Nevažeći kod karte: {card}, {str(e)}")
            
            # Provjeri da igrač nema već tu kartu
            card_code = card.get_code() if hasattr(card, 'get_code') else str(card)
            if self.has_card(card_code):
                logger.debug(f"Igrač {self.username} već ima kartu {card_code}")
                return False
            
            self.hand.append(card)
            
            # Invalidacija keša
            self._invalidate_cache()
            
            logger.debug(f"Igrač {self.username} dobio kartu {card_code}, trenutno ima {len(self.hand)} karata")
            return True
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri dodavanju karte igraču {self.username}: {str(e)}", exc_info=True)
            return False
    
    @track_execution_time
    def remove_card(self, card):
        """
        Uklanja kartu iz ruke igrača.
        
        Args:
            card (Card or str): Karta koja se uklanja (objekt Card ili string)
            
        Returns:
            Card: Uklonjena karta ili None ako karta nije pronađena
            
        Raises:
            ValueError: Ako je format karte nevažeći ili karta nije pronađena
        """
        try:
            # Pretvori string u kod karte ako je potrebno
            if isinstance(card, str):
                card_code = card
                card_found = False
                
                for i, c in enumerate(self.hand):
                    c_code = c.get_code() if hasattr(c, 'get_code') else str(c)
                    if c_code == card_code:
                        card_found = True
                        removed_card = self.hand.pop(i)
                        
                        # Invalidacija keša
                        self._invalidate_cache()
                        
                        logger.debug(f"Igrač {self.username} uklonio kartu {card_code}, preostalo {len(self.hand)} karata")
                        return removed_card
                
                if not card_found:
                    logger.warning(f"Karta {card_code} nije pronađena u ruci igrača {self.username}")
                    return None
            
            # Ako je objekt Card
            if card in self.hand:
                self.hand.remove(card)
                
                # Invalidacija keša
                self._invalidate_cache()
                
                card_code = card.get_code() if hasattr(card, 'get_code') else str(card)
                logger.debug(f"Igrač {self.username} uklonio kartu {card_code}, preostalo {len(self.hand)} karata")
                return card
            
            logger.warning(f"Karta {card} nije pronađena u ruci igrača {self.username}")
            return None
        except Exception as e:
            logger.error(f"Greška pri uklanjanju karte od igrača {self.username}: {str(e)}", exc_info=True)
            return None
    
    @track_execution_time
    def has_card(self, card):
        """
        Provjerava ima li igrač određenu kartu.
        
        Args:
            card (Card or str): Karta koja se provjerava (objekt Card ili string)
            
        Returns:
            bool: True ako igrač ima kartu, False inače
        """
        try:
            # Pretvori string u kod karte ako je potrebno
            if isinstance(card, str):
                card_code = card
                for c in self.hand:
                    c_code = c.get_code() if hasattr(c, 'get_code') else str(c)
                    if c_code == card_code:
                        return True
                return False
            
            # Ako je objekt Card
            return card in self.hand
        except Exception as e:
            logger.error(f"Greška pri provjeri karte u ruci igrača {self.username}: {str(e)}", exc_info=True)
            return False
    
    @track_execution_time
    def get_cards_of_suit(self, suit):
        """
        Vraća sve karte određene boje iz ruke igrača.
        
        Args:
            suit (str): Boja koja se traži ('S', 'H', 'D', 'C')
            
        Returns:
            list: Lista karata tražene boje
            
        Raises:
            ValueError: Ako je boja nevažeća
        """
        try:
            # Validacija boje
            if suit not in Card.VALID_SUITS:
                error_msg = f"Nevažeća boja: {suit}. Dozvoljene boje: {Card.VALID_SUITS}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Koristi keš ako postoji
            if suit in self._hand_by_suit and self._hand_by_suit[suit]['timestamp'] == self._cache_timestamp:
                return self._hand_by_suit[suit]['cards']
            
            # Inače, filtriraj karte
            cards_of_suit = [card for card in self.hand if card.suit == suit]
            
            # Spremi u keš
            self._hand_by_suit[suit] = {
                'timestamp': self._cache_timestamp,
                'cards': cards_of_suit
            }
            
            return cards_of_suit
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju karata boje {suit} za igrača {self.username}: {str(e)}", exc_info=True)
            return []
    
    @track_execution_time
    def has_suit(self, suit):
        """
        Provjerava ima li igrač karte određene boje.
        
        Args:
            suit (str): Boja koja se provjerava ('S', 'H', 'D', 'C')
            
        Returns:
            bool: True ako igrač ima barem jednu kartu tražene boje, False inače
            
        Raises:
            ValueError: Ako je boja nevažeća
        """
        try:
            # Validacija boje
            if suit not in Card.VALID_SUITS:
                error_msg = f"Nevažeća boja: {suit}. Dozvoljene boje: {Card.VALID_SUITS}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Koristi get_cards_of_suit jer već ima keširanje
            return len(self.get_cards_of_suit(suit)) > 0
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri provjeri ima li igrač {self.username} boju {suit}: {str(e)}", exc_info=True)
            return False
    
    @track_execution_time
    def can_play_card(self, card, trick, trump_suit):
        """
        Provjerava može li igrač odigrati određenu kartu prema pravilima igre.
        
        Args:
            card (Card or str): Karta koju igrač želi odigrati
            trick (list): Trenutni štih (lista već odigranih karata)
            trump_suit (str): Adutska boja
            
        Returns:
            bool: True ako se karta može odigrati, False inače
            
        Raises:
            ValueError: Ako je format karte nevažeći ili ako su parametri nevažeći
        """
        try:
            # Pretvori string u objekt Card ako je potrebno
            if isinstance(card, str):
                try:
                    card_code = card
                    card_obj = None
                    
                    for c in self.hand:
                        c_code = c.get_code() if hasattr(c, 'get_code') else str(c)
                        if c_code == card_code:
                            card_obj = c
                            break
                    
                    if not card_obj:
                        logger.warning(f"Karta {card_code} nije pronađena u ruci igrača {self.username}")
                        return False
                    
                    card = card_obj
                except Exception as e:
                    logger.warning(f"Greška pri pretvaranju koda karte {card}: {str(e)}")
                    return False
            
            # Ako igrač nema kartu u ruci, ne može ju odigrati
            if card not in self.hand:
                logger.debug(f"Igrač {self.username} nema kartu {card} u ruci")
                return False
            
            # Validacija adutske boje
            if trump_suit and trump_suit not in Card.VALID_SUITS:
                error_msg = f"Nevažeća adutska boja: {trump_suit}. Dozvoljene boje: {Card.VALID_SUITS}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Validacija štiha
            if trick is None:
                trick = []
                
            # Ako je prvi potez u štihu, može se odigrati bilo koja karta
            if not trick:
                return True
            
            # Prva karta u štihu određuje traženu boju
            lead_card = trick[0]
            if isinstance(lead_card, tuple):  # Ako je format (igrač, karta)
                lead_card = lead_card[1]
                
            lead_suit = lead_card.suit if hasattr(lead_card, 'suit') else lead_card.split()[0][-1]
            
            # Ako igrač ima traženu boju, mora ju igrati
            if self.has_suit(lead_suit):
                return card.suit == lead_suit
            
            # Ako igrač nema traženu boju i adut još nije igran, mora igrati aduta ako ga ima
            if trump_suit:
                adut_played = any(
                    (c[1].suit if isinstance(c, tuple) else c.suit) == trump_suit 
                    for c in trick
                )
                
                if not adut_played and self.has_suit(trump_suit):
                    return card.suit == trump_suit
            
            # Ako igrač nema ni traženu boju ni aduta, može igrati bilo koju kartu
            return True
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri provjeri može li igrač {self.username} odigrati kartu {card}: {str(e)}", exc_info=True)
            return False
    
    @track_execution_time
    def play_card(self, card, trick, trump_suit):
        """
        Igra kartu iz ruke igrača.
        
        Args:
            card (Card or str): Karta koju igrač želi odigrati
            trick (list): Trenutni štih (lista već odigranih karata)
            trump_suit (str): Adutska boja
            
        Returns:
            Card: Odigrana karta ili None ako potez nije valjan
            
        Raises:
            ValueError: Ako potez nije valjan prema pravilima igre
        """
        try:
            # Pretvori string u objekt Card ako je potrebno
            if isinstance(card, str):
                card_code = card
                card_obj = None
                
                for c in self.hand:
                    c_code = c.get_code() if hasattr(c, 'get_code') else str(c)
                    if c_code == card_code:
                        card_obj = c
                        break
                
                if not card_obj:
                    error_msg = f"Karta {card_code} nije pronađena u ruci igrača {self.username}"
                    logger.warning(error_msg)
                    raise ValueError(error_msg)
                
                card = card_obj
            
            # Provjeri može li se karta odigrati
            if not self.can_play_card(card, trick, trump_suit):
                error_msg = f"Potez nije valjan prema pravilima igre: {card}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Ukloni kartu iz ruke i vrati je
            played_card = self.remove_card(card)
            
            # Log odigranog poteza
            card_code = card.get_code() if hasattr(card, 'get_code') else str(card)
            logger.info(f"Igrač {self.username} odigrao kartu {card_code}")
            
            return played_card
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri igranju karte za igrača {self.username}: {str(e)}", exc_info=True)
            raise
    
    @track_execution_time
    def clear_hand(self):
        """
        Uklanja sve karte iz ruke igrača.
        
        Returns:
            list: Lista uklonjenih karata
        """
        try:
            cards = self.hand.copy()
            self.hand = []
            
            # Invalidacija keša
            self._invalidate_cache()
            
            logger.debug(f"Ruka igrača {self.username} očišćena, uklonjeno {len(cards)} karata")
            return cards
        except Exception as e:
            logger.error(f"Greška pri čišćenju ruke igrača {self.username}: {str(e)}", exc_info=True)
            return []
    
    @track_execution_time
    def set_team(self, team):
        """
        Postavlja tim kojem igrač pripada.
        
        Args:
            team (str): Oznaka tima ('a' ili 'b')
            
        Returns:
            bool: True ako je tim uspješno postavljen, False inače
            
        Raises:
            ValueError: Ako je tim nevažeći
        """
        try:
            if team not in [self.TEAM_A, self.TEAM_B]:
                error_msg = f"Nevažeći tim: {team}. Dozvoljeni timovi: {self.TEAM_A}, {self.TEAM_B}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            self.team = team
            logger.info(f"Igrač {self.username} dodijeljen timu {team}")
            return True
        except ValueError as e:
            # Prosljeđivanje ValueError-a
            raise
        except Exception as e:
            logger.error(f"Greška pri postavljanju tima za igrača {self.username}: {str(e)}", exc_info=True)
            return False
    
    @track_execution_time
    def sort_hand(self):
        """
        Sortira karte u ruci igrača.
        
        Sortira karte po boji (pik, herc, karo, tref) i po vrijednosti
        unutar boje (7, 8, 9, 10, J, Q, K, A).
        
        Returns:
            list: Sortirana ruka
        """
        try:
            # Sortiranje karte prvo po boji, zatim po vrijednosti
            self.hand.sort(key=lambda card: (
                self.SUIT_ORDER[card.suit], 
                self.VALUE_ORDER[card.value]
            ))
            
            # Invalidacija keša jer je redoslijed promijenjen
            self._invalidate_cache()
            
            logger.debug(f"Ruka igrača {self.username} sortirana, {len(self.hand)} karata")
            return self.hand
        except Exception as e:
            logger.error(f"Greška pri sortiranju ruke igrača {self.username}: {str(e)}", exc_info=True)
            # U slučaju greške, vrati trenutnu ruku bez sortiranja
            return self.hand
    
    @track_execution_time
    def update_stats(self, game_won):
        """
        Ažurira statistiku igrača nakon igre.
        
        Args:
            game_won (bool): True ako je igrač pobijedio, False inače
            
        Returns:
            dict: Ažurirana statistika igrača
        """
        try:
            self.games_played += 1
            
            if game_won:
                self.games_won += 1
                self.score += 1
            
            win_rate = (self.games_won / self.games_played) * 100 if self.games_played > 0 else 0
            
            stats = {
                'games_played': self.games_played,
                'games_won': self.games_won,
                'score': self.score,
                'win_rate': round(win_rate, 2)
            }
            
            logger.info(f"Statistika igrača {self.username} ažurirana: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Greška pri ažuriranju statistike igrača {self.username}: {str(e)}", exc_info=True)
            return {
                'games_played': self.games_played,
                'games_won': self.games_won,
                'score': self.score,
                'error': str(e)
            }
    
    def __str__(self):
        """
        Vraća string reprezentaciju igrača.
        
        Returns:
            str: String s osnovnim informacijama o igraču
        """
        return f"{self.username} (Tim: {self.team}, Karata: {len(self.hand)})"
    
    def __repr__(self):
        """
        Vraća reprezentaciju igrača za debagiranje.
        
        Returns:
            str: String s detaljnim informacijama o igraču
        """
        return f"Player(id='{self.id}', username='{self.username}', team='{self.team}', cards={len(self.hand)})"
    
    def __eq__(self, other):
        """
        Provjerava jesu li dva igrača jednaka.
        
        Args:
            other: Drugi igrač za usporedbu
            
        Returns:
            bool: True ako su igrači jednaki (isti ID), False inače
        """
        if not isinstance(other, Player):
            return False
        return self.id == other.id
    
    def __hash__(self):
        """
        Vraća hash vrijednost igrača.
        
        Returns:
            int: Hash vrijednost temeljena na ID-u igrača
        """
        return hash(self.id)