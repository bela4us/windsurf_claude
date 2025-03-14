"""
Modul koji definira bodovanje u Belot igri.

Ovaj modul pruža implementaciju klase Scoring koja sadrži logiku za
izračun bodova u igri Belot, uključujući bodovanje karata, zvanja i štihova.
"""

import logging
from functools import lru_cache
from game.game_logic.card import Card
from utils.decorators import track_execution_time

# Konfiguracija loggera
logger = logging.getLogger(__name__)

class Scoring:
    """
    Klasa koja definira bodovanje u Belot igri.
    
    Sadrži metode za izračun bodova za karte, štihove i zvanja.
    
    Attributes:
        NON_TRUMP_POINTS (dict): Bodovna vrijednost karata kada boja nije adut
        TRUMP_POINTS (dict): Bodovna vrijednost karata kada je boja adut
        DECLARATION_POINTS (dict): Bodovna vrijednost zvanja
        LAST_TRICK_BONUS (int): Dodatni bodovi za zadnji štih
        CLEAN_SWEEP_BONUS (int): Bodovi za štih-mač (štiglju)
        SUIT_MAP (dict): Mapiranje punih imena boja na kodove
        _cache_timestamp (float): Vremenska oznaka za invalidaciju keša
    """
    
    # Bodovna vrijednost karata kada boja nije adut
    NON_TRUMP_POINTS = {
        'A': 11, '10': 10, 'K': 4, 'Q': 3, 'J': 2, '9': 0, '8': 0, '7': 0
    }
    
    # Bodovna vrijednost karata kada je boja adut
    TRUMP_POINTS = {
        'J': 20, '9': 14, 'A': 11, '10': 10, 'K': 4, 'Q': 3, '8': 0, '7': 0
    }
    
    # Bodovna vrijednost zvanja
    DECLARATION_POINTS = {
        'belot': 1001,        # Osam karata u istoj boji u nizu
        'four_jacks': 200,    # Četiri dečka
        'four_nines': 150,    # Četiri devetke
        'four_aces': 100,     # Četiri asa
        'four_tens': 100,     # Četiri desetke
        'four_kings': 100,    # Četiri kralja
        'four_queens': 100,   # Četiri dame
        'sequence_5_plus': 100,  # Pet ili više karata u istoj boji u nizu
        'sequence_4': 50,     # Četiri karte u istoj boji u nizu
        'sequence_3': 20,     # Tri karte u istoj boji u nizu
        'bela': 20            # Kralj i dama iste boje u adutu
    }
    
    # Dodatni bodovi za zadnji štih
    LAST_TRICK_BONUS = 10
    
    # Bodovi za štih-mač (štiglju)
    CLEAN_SWEEP_BONUS = 90
    
    # Mapiranje punih imena boja na kodove
    SUIT_MAP = {
        'spades': 'S',
        'hearts': 'H',
        'diamonds': 'D',
        'clubs': 'C'
    }
    
    @track_execution_time
    def __init__(self):
        """Inicijalizira objekt bodovanja igre."""
        self._cache_timestamp = 0.0
        logger.debug("Inicijalizirani objekt bodovanja igre")
    
    def _invalidate_cache(self):
        """Invalidira sve kešove povezane s objektom bodovanja."""
        import time
        self._cache_timestamp = time.time()
        # Briše sve keširane vrijednosti pozivanjem odgovarajućih clear metoda
        self.get_card_point_value.cache_clear()
        self._normalize_suit.cache_clear()
        logger.debug("Keš bodovanja igre invalidiran")
    
    @track_execution_time
    @lru_cache(maxsize=128)
    def get_card_point_value(self, card, trump_suit):
        """
        Vraća bodovnu vrijednost karte.
        
        Args:
            card (Card): Karta čija se vrijednost određuje
            trump_suit (str): Adutska boja
            
        Returns:
            int: Bodovna vrijednost karte
            
        Raises:
            ValueError: Ako je karta nevažeća ili adutska boja nevažeća
        """
        try:
            # Validacija karte
            if not hasattr(card, 'suit') or not hasattr(card, 'value'):
                error_msg = f"Nevažeća karta: {card}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Normalizacija trump_suit iz punog imena u kod
            trump_suit_code = self._normalize_suit(trump_suit)
            
            # Određivanje je li karta adut
            is_trump = (card.suit == trump_suit_code)
            
            # Odabir odgovarajućeg rječnika bodova
            points_dict = self.TRUMP_POINTS if is_trump else self.NON_TRUMP_POINTS
            
            # Dohvaćanje bodovne vrijednosti
            points = points_dict.get(card.value, 0)
            
            return points
        except Exception as e:
            logger.error(f"Greška pri dohvatu bodovne vrijednosti karte: {str(e)}", exc_info=True)
            return 0  # U slučaju greške, vraćamo 0 bodova
    
    @track_execution_time
    def calculate_trick_points(self, trick, trump_suit, is_last_trick=False):
        """
        Izračunava ukupne bodove za štih.
        
        Args:
            trick (list): Lista poteza u štihu (lista Card objekata)
            trump_suit (str): Adutska boja
            is_last_trick (bool): Je li ovo zadnji štih u rundi
            
        Returns:
            int: Ukupni bodovi za štih
            
        Raises:
            ValueError: Ako je štih prazan ili sadrži nevažeće karte
        """
        try:
            # Validacija štiha
            if not trick:
                logger.debug("Štih je prazan, nema bodova")
                return 0
            
            # Normalizacija trump_suit iz punog imena u kod
            trump_suit_code = self._normalize_suit(trump_suit)
            
            # Izračunavanje bodova za karte u štihu
            points = sum(self.get_card_point_value(card, trump_suit_code) for card in trick)
            
            # Dodavanje bodova za zadnji štih
            if is_last_trick:
                points += self.LAST_TRICK_BONUS
                logger.debug(f"Dodan bonus za zadnji štih: {self.LAST_TRICK_BONUS}")
            
            logger.debug(f"Ukupno bodova za štih: {points}")
            return points
        except Exception as e:
            logger.error(f"Greška pri izračunu bodova za štih: {str(e)}", exc_info=True)
            return 0  # U slučaju greške, vraćamo 0 bodova
    
    @track_execution_time
    def calculate_declaration_points(self, declarations):
        """
        Izračunava ukupne bodove za zvanja.
        
        Args:
            declarations (list): Lista zvanja (rječnici s tipom i vrijednošću)
            
        Returns:
            int: Ukupni bodovi za zvanja
            
        Raises:
            ValueError: Ako declarations nije lista ili je nevažećeg formata
        """
        try:
            # Validacija zvanja
            if not declarations:
                logger.debug("Nema zvanja, bodovi su 0")
                return 0
            
            if not isinstance(declarations, list):
                error_msg = f"Parametar declarations mora biti lista, a dobiven je {type(declarations)}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Izračun bodova za sva zvanja
            points = sum(decl.get('value', 0) for decl in declarations)
            
            logger.debug(f"Ukupno bodova za zvanja: {points}")
            return points
        except Exception as e:
            logger.error(f"Greška pri izračunu bodova za zvanja: {str(e)}", exc_info=True)
            return 0  # U slučaju greške, vraćamo 0 bodova
    
    @track_execution_time
    def add_last_trick_bonus(self, points):
        """
        Dodaje bonus bodove za zadnji štih.
        
        Args:
            points (int): Osnovni bodovi
            
        Returns:
            int: Bodovi s dodanim bonusom
            
        Raises:
            ValueError: Ako points nije cijeli broj
        """
        try:
            if not isinstance(points, int):
                error_msg = f"Parametar points mora biti cijeli broj, a dobiven je {type(points)}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            total = points + self.LAST_TRICK_BONUS
            logger.debug(f"Dodani bonus bodovi za zadnji štih: {points} + {self.LAST_TRICK_BONUS} = {total}")
            return total
        except Exception as e:
            logger.error(f"Greška pri dodavanju bonusa za zadnji štih: {str(e)}", exc_info=True)
            return points  # U slučaju greške, vraćamo originalni broj bodova
    
    @track_execution_time
    def check_belot_bonus(self, hand, trump_suit):
        """
        Provjerava i vraća bodove za belot (kralj i dama u adutu).
        
        Args:
            hand (list): Lista karata u ruci igrača
            trump_suit (str): Adutska boja
            
        Returns:
            int: Bodovi za belot (20 ili 0)
            
        Raises:
            ValueError: Ako je ruka prazna ili adutska boja nevažeća
        """
        try:
            # Validacija parametara
            if not hand:
                logger.debug("Ruka je prazna, nema belota")
                return 0
            
            if not trump_suit:
                logger.debug("Adutska boja nije zadana, nema belota")
                return 0
            
            # Normalizacija adutske boje
            trump_suit_code = self._normalize_suit(trump_suit)
            
            # Pronađi sve karte aduta
            trump_cards = [card for card in hand if card.suit == trump_suit_code]
            
            # Provjeri ima li igrač kralja i damu u adutu
            has_king = any(card.value == 'K' for card in trump_cards)
            has_queen = any(card.value == 'Q' for card in trump_cards)
            
            if has_king and has_queen:
                logger.debug(f"Pronađen belot u boji {trump_suit_code}, dodano {self.DECLARATION_POINTS['bela']} bodova")
                return self.DECLARATION_POINTS['bela']
            
            logger.debug(f"Nije pronađen belot u boji {trump_suit_code}")
            return 0
        except Exception as e:
            logger.error(f"Greška pri provjeri belot bonusa: {str(e)}", exc_info=True)
            return 0  # U slučaju greške, vraćamo 0 bodova
    
    @track_execution_time
    def check_declarations_priority(self, team_a_declarations, team_b_declarations):
        """
        Određuje koji tim ima prioritet kod zvanja.
        
        Prema pravilima, ako oba tima imaju zvanja iste vrijednosti,
        prioritet ima tim koji je bliži djelitelju.
        
        Args:
            team_a_declarations (list): Lista zvanja tima A
            team_b_declarations (list): Lista zvanja tima B
            
        Returns:
            str: Tim s prioritetom ('a' ili 'b'), ili None ako su zvanja jednaka
            
        Raises:
            ValueError: Ako parametri nisu liste
        """
        try:
            # Validacija parametara
            if not isinstance(team_a_declarations, list) or not isinstance(team_b_declarations, list):
                error_msg = "Parametri moraju biti liste zvanja"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Ako nema zvanja, nema prioriteta
            if not team_a_declarations and not team_b_declarations:
                logger.debug("Oba tima nemaju zvanja, nema prioriteta")
                return None
            
            # Pronađi najvišu vrijednost zvanja za svaki tim
            team_a_max = max([decl.get('value', 0) for decl in team_a_declarations], default=0)
            team_b_max = max([decl.get('value', 0) for decl in team_b_declarations], default=0)
            
            if team_a_max > team_b_max:
                logger.debug(f"Tim A ima prioritet sa zvanjem vrijednosti {team_a_max}")
                return 'a'
            elif team_b_max > team_a_max:
                logger.debug(f"Tim B ima prioritet sa zvanjem vrijednosti {team_b_max}")
                return 'b'
            elif team_a_max == team_b_max and team_a_max > 0:
                # Ako su zvanja jednake vrijednosti, potrebno je implementirati
                # logiku prioriteta prema blizini djelitelju (ovo ovisi o implementaciji igre)
                # Za sada vraćamo None (jednako)
                logger.debug(f"Oba tima imaju zvanje iste vrijednosti ({team_a_max}), potrebno je odrediti prioritet prema blizini djelitelju")
                return None
            else:
                logger.debug("Nema zvanja s prioritetom")
                return None
        except Exception as e:
            logger.error(f"Greška pri određivanju prioriteta zvanja: {str(e)}", exc_info=True)
            return None  # U slučaju greške, vraćamo None
    
    @track_execution_time
    def calculate_round_score(self, team_a_tricks, team_b_tricks, team_a_declarations, team_b_declarations, calling_team):
        """
        Izračunava ukupne bodove za rundu.
        
        Args:
            team_a_tricks (list): Lista štihova tima A
            team_b_tricks (list): Lista štihova tima B
            team_a_declarations (list): Lista zvanja tima A
            team_b_declarations (list): Lista zvanja tima B
            calling_team (str): Tim koji je zvao aduta ('a' ili 'b')
            
        Returns:
            tuple: (bodovi_tim_a, bodovi_tim_b, pobjednički_tim)
            
        Raises:
            ValueError: Ako parametri nisu odgovarajućeg tipa ili imaju nevažeće vrijednosti
        """
        try:
            # Validacija parametara
            if not isinstance(team_a_tricks, list) or not isinstance(team_b_tricks, list):
                error_msg = "Parametri štihova moraju biti liste"
                logger.warning(error_msg)
                raise ValueError(error_msg)
                
            if not isinstance(team_a_declarations, list) or not isinstance(team_b_declarations, list):
                error_msg = "Parametri zvanja moraju biti liste"
                logger.warning(error_msg)
                raise ValueError(error_msg)
                
            if calling_team not in ['a', 'b']:
                error_msg = f"Nevažeći tim koji je zvao aduta: {calling_team}, mora biti 'a' ili 'b'"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Izračunavanje bodova za štihove
            team_a_trick_points = sum(trick.get('points', 0) for trick in team_a_tricks)
            team_b_trick_points = sum(trick.get('points', 0) for trick in team_b_tricks)
            
            logger.debug(f"Bodovi za štihove - Tim A: {team_a_trick_points}, Tim B: {team_b_trick_points}")
            
            # Provjera štih-mača (štiglje)
            if not team_a_tricks and team_b_tricks:
                team_b_trick_points += self.CLEAN_SWEEP_BONUS
                logger.debug(f"Tim B dobio bonus za štih-mač: {self.CLEAN_SWEEP_BONUS}")
            elif not team_b_tricks and team_a_tricks:
                team_a_trick_points += self.CLEAN_SWEEP_BONUS
                logger.debug(f"Tim A dobio bonus za štih-mač: {self.CLEAN_SWEEP_BONUS}")
            
            # Izračunavanje bodova za zvanja
            team_a_declaration_points = sum(decl.get('value', 0) for decl in team_a_declarations)
            team_b_declaration_points = sum(decl.get('value', 0) for decl in team_b_declarations)
            
            logger.debug(f"Bodovi za zvanja - Tim A: {team_a_declaration_points}, Tim B: {team_b_declaration_points}")
            
            # Bodovi s zvanjima
            team_a_points = team_a_trick_points + team_a_declaration_points
            team_b_points = team_b_trick_points + team_b_declaration_points
            
            logger.debug(f"Ukupni bodovi prije primjene pravila prolaza - Tim A: {team_a_points}, Tim B: {team_b_points}")
            
            # Primjena pravila "prolaza"
            if calling_team == 'a':
                if team_a_points <= team_b_points:
                    # Tim A nije prošao, svi bodovi idu timu B
                    total_points = team_a_points + team_b_points
                    team_b_points = total_points
                    team_a_points = 0
                    winner_team = 'b'
                    logger.debug(f"Tim A nije prošao, svi bodovi ({total_points}) idu timu B")
                else:
                    winner_team = 'a'
                    logger.debug(f"Tim A je prošao, zadržava svoje bodove: {team_a_points}")
            else:  # calling_team == 'b'
                if team_b_points <= team_a_points:
                    # Tim B nije prošao, svi bodovi idu timu A
                    total_points = team_a_points + team_b_points
                    team_a_points = total_points
                    team_b_points = 0
                    winner_team = 'a'
                    logger.debug(f"Tim B nije prošao, svi bodovi ({total_points}) idu timu A")
                else:
                    winner_team = 'b'
                    logger.debug(f"Tim B je prošao, zadržava svoje bodove: {team_b_points}")
            
            logger.info(f"Konačni rezultat runde - Tim A: {team_a_points}, Tim B: {team_b_points}, Pobjednik: Tim {winner_team.upper()}")
            return team_a_points, team_b_points, winner_team
        except Exception as e:
            logger.error(f"Greška pri izračunu bodova za rundu: {str(e)}", exc_info=True)
            # U slučaju greške, vraćamo nulu za oba tima i None za pobjednika
            return 0, 0, None
    
    @track_execution_time
    @lru_cache(maxsize=32)
    def get_declaration_value(self, declaration_type, cards=None):
        """
        Vraća bodovnu vrijednost zvanja.
        
        Args:
            declaration_type (str): Tip zvanja (npr. 'sequence_3', 'four_jacks')
            cards (list, optional): Lista karata koje čine zvanje (opcionalano)
            
        Returns:
            int: Bodovna vrijednost zvanja
            
        Raises:
            ValueError: Ako je tip zvanja nevažeći
        """
        try:
            # Validacija tipa zvanja
            if declaration_type not in self.DECLARATION_POINTS:
                logger.warning(f"Nevažeći tip zvanja: {declaration_type}")
                return 0
            
            value = self.DECLARATION_POINTS.get(declaration_type, 0)
            logger.debug(f"Vrijednost zvanja {declaration_type}: {value}")
            return value
        except Exception as e:
            logger.error(f"Greška pri dohvatu vrijednosti zvanja: {str(e)}", exc_info=True)
            return 0  # U slučaju greške, vraćamo 0 bodova
    
    @lru_cache(maxsize=64)
    def _normalize_suit(self, suit):
        """
        Pretvara puno ime boje u kod boje.
        
        Args:
            suit (str): Boja (puno ime ili kod)
            
        Returns:
            str: Kod boje ('S', 'H', 'D', 'C')
            
        Raises:
            ValueError: Ako je boja nevažeća
        """
        try:
            if not suit:
                return None
                
            # Ako je već kod, vrati ga
            if suit in Card.VALID_SUITS:
                return suit
            
            # Inače pokušaj mapirati iz punog imena
            normalized = self.SUIT_MAP.get(suit.lower(), suit)
            
            # Provjera je li normalizirana boja valjana
            if normalized not in Card.VALID_SUITS:
                logger.warning(f"Nevažeća boja: {suit} (normalizirano u {normalized})")
            
            return normalized
        except Exception as e:
            logger.error(f"Greška pri normalizaciji boje: {str(e)}", exc_info=True)
            return suit  # U slučaju greške, vrati izvornu vrijednost