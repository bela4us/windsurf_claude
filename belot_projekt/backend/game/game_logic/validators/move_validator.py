"""
Modul koji definira validator poteza u Belot igri.

Ovaj modul pruža implementaciju klase MoveValidator koja je odgovorna za
provjeru valjanosti poteza (igranja karata) prema pravilima Belot igre.
Validator osigurava da igrači poštuju pravila o praćenju boje, bacanju aduta
i igranju jačih karata kada je to potrebno.
"""

import logging
from functools import lru_cache
from game.game_logic.card import Card
from game.game_logic.rules import Rules
from utils.decorators import track_execution_time

# Konfiguracija loggera
logger = logging.getLogger(__name__)

class MoveValidator:
    """
    Klasa koja validira poteze u Belot igri.
    
    Provjerava jesu li potezi (igranje karata) valjani prema pravilima
    Belota, uključujući praćenje boje, bacanje aduta, i pravilo 'übera'.
    
    Attributes:
        rules (Rules): Instanca klase Rules za provjeru pravila
        SUIT_MAP (dict): Mapiranje punih imena boja na kodove
        SUIT_NAMES (dict): Mapiranje kodova boje na hrvatska imena
        _cache_timestamp (float): Vremenska oznaka za invalidaciju keša
    """
    
    # Mapiranje punih imena boja na kodove
    SUIT_MAP = {
        'spades': 'S',
        'hearts': 'H',
        'diamonds': 'D',
        'clubs': 'C'
    }
    
    # Mapiranje kodova boje na hrvatska imena
    SUIT_NAMES = {
        'S': 'pik',
        'H': 'herc',
        'D': 'karo',
        'C': 'tref'
    }
    
    @track_execution_time
    def __init__(self):
        """Inicijalizira validator poteza."""
        self.rules = Rules()  # Koristimo Rules klasu za provjeru pravila
        self._cache_timestamp = 0.0
        logger.debug("Inicijaliziran validator poteza")
    
    def _invalidate_cache(self):
        """Invalidira sve kešove povezane s validatorom poteza."""
        import time
        self._cache_timestamp = time.time()
        # Briše sve keširane vrijednosti pozivanjem odgovarajućih clear metoda
        self._normalize_suit.cache_clear()
        self._suit_name.cache_clear()
        logger.debug("Keš validatora poteza invalidiran")
    
    @track_execution_time
    def validate(self, card, hand, trick, trump_suit):
        """
        Glavna metoda validacije poteza (alias za validate_move).
        
        Args:
            card (Card): Karta koju igrač želi odigrati
            hand (list): Lista karata u ruci igrača
            trick (list): Lista već odigranih karata u trenutnom štihu
            trump_suit (str): Adutska boja
            
        Returns:
            tuple: (bool, str) - (je li potez valjan, razlog ako nije)
            
        Raises:
            ValueError: Ako su parametri nevažeći
        """
        try:
            # Validacija parametara
            if not isinstance(hand, list):
                error_msg = f"Parametar hand mora biti lista, a dobiven je {type(hand)}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
                
            if not isinstance(trick, list) and trick is not None:
                error_msg = f"Parametar trick mora biti lista ili None, a dobiven je {type(trick)}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Proslijedi validaciju na validate_move
            result = self.validate_move(card, hand, trick, trump_suit)
            logger.debug(f"Validacija poteza: {result}")
            return result
        except Exception as e:
            logger.error(f"Greška pri validaciji poteza: {str(e)}", exc_info=True)
            return False, f"Greška pri validaciji: {str(e)}"
    
    @track_execution_time
    def can_play_card(self, card, hand, trick, trump_suit):
        """
        Provjerava može li se karta odigrati prema pravilima.
        
        Args:
            card (Card): Karta koju igrač želi odigrati
            hand (list): Lista karata u ruci igrača
            trick (list): Lista već odigranih karata u trenutnom štihu
            trump_suit (str): Adutska boja
            
        Returns:
            bool: True ako se karta može odigrati, False inače
            
        Raises:
            ValueError: Ako su parametri nevažeći
        """
        try:
            valid, reason = self.validate_move(card, hand, trick, trump_suit)
            if not valid:
                logger.debug(f"Karta {card} ne može se odigrati: {reason}")
            return valid
        except Exception as e:
            logger.error(f"Greška pri provjeri može li se karta odigrati: {str(e)}", exc_info=True)
            return False
    
    @track_execution_time
    def must_follow_suit(self, hand, lead_suit, trump_suit):
        """
        Vraća karte koje igrač može igrati poštujući pravilo praćenja boje.
        
        Args:
            hand (list): Lista karata u ruci igrača
            lead_suit (str): Tražena boja (boja prve karte u štihu)
            trump_suit (str): Adutska boja
            
        Returns:
            list: Lista karata koje igrač može odigrati
            
        Raises:
            ValueError: Ako su parametri nevažeći
        """
        try:
            # Validacija parametara
            if not isinstance(hand, list):
                error_msg = f"Parametar hand mora biti lista, a dobiven je {type(hand)}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
                
            if not hand:
                logger.debug("Ruka je prazna, nema karata za igrati")
                return []
            
            # Normalizacija boja
            lead_suit_code = self._normalize_suit(lead_suit)
            trump_suit_code = self._normalize_suit(trump_suit)
            
            # Provjeri ima li igrač karte tražene boje
            lead_suit_cards = [card for card in hand if card.suit == lead_suit_code]
            if lead_suit_cards:
                logger.debug(f"Igrač mora igrati boju {lead_suit_code}, pronađeno {len(lead_suit_cards)} odgovarajućih karata")
                return lead_suit_cards
            
            # Ako nema karte tražene boje, treba igrati aduta ako ga ima
            trump_cards = [card for card in hand if card.suit == trump_suit_code]
            if trump_cards:
                logger.debug(f"Igrač nema boju {lead_suit_code}, ali mora igrati aduta {trump_suit_code}, pronađeno {len(trump_cards)} aduta")
                return trump_cards
            
            # Ako nema ni traženu boju ni aduta, može baciti bilo koju kartu
            logger.debug(f"Igrač nema ni boju {lead_suit_code} ni aduta {trump_suit_code}, može igrati bilo koju kartu")
            return hand
        except Exception as e:
            logger.error(f"Greška pri određivanju karata koje igrač može odigrati: {str(e)}", exc_info=True)
            return hand  # U slučaju greške, vrati sve karte
    
    @track_execution_time
    def can_trump(self, hand, lead_suit, trump_suit, trick=None):
        """
        Provjerava može li i mora li igrač igrati aduta.
        
        Args:
            hand (list): Lista karata u ruci igrača
            lead_suit (str): Tražena boja (boja prve karte u štihu)
            trump_suit (str): Adutska boja
            trick (list, optional): Lista karata već odigranih u štihu (opcionalno)
            
        Returns:
            tuple: (bool, bool) - (može li rezati, mora li rezati)
            
        Raises:
            ValueError: Ako su parametri nevažeći
        """
        try:
            # Validacija parametara
            if not isinstance(hand, list):
                error_msg = f"Parametar hand mora biti lista, a dobiven je {type(hand)}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
                
            if not hand:
                logger.debug("Ruka je prazna, igrač ne može i ne mora rezati")
                return False, False
            
            # Normalizacija boja
            lead_suit_code = self._normalize_suit(lead_suit)
            trump_suit_code = self._normalize_suit(trump_suit)
            
            # Provjeri ima li igrač karte tražene boje
            has_lead_suit = any(card.suit == lead_suit_code for card in hand)
            
            # Ako ima traženu boju, ne smije rezati
            if has_lead_suit:
                logger.debug(f"Igrač ima boju {lead_suit_code}, ne smije rezati")
                return False, False
                
            # Provjeri ima li aduta
            has_trump = any(card.suit == trump_suit_code for card in hand)
            if not has_trump:
                logger.debug(f"Igrač nema aduta {trump_suit_code}, ne može rezati")
                return False, False
                
            # Ako nema traženu boju ali ima aduta, ovisi je li adut već igran
            if trick:
                # Provjeri je li adut već igran
                adut_already_played = any(card.suit == trump_suit_code for card in trick)
                if adut_already_played:
                    # Ako je adut već igran, može, ali ne mora rezati
                    logger.debug(f"Adut {trump_suit_code} je već igran, igrač može ali ne mora rezati")
                    return True, False
                    
            # Ako nema traženu boju i ima aduta i adut nije igran, mora rezati
            logger.debug(f"Igrač nema boju {lead_suit_code}, ima aduta {trump_suit_code} i adut nije još igran, mora rezati")
            return True, True
        except Exception as e:
            logger.error(f"Greška pri provjeri može li i mora li igrač rezati: {str(e)}", exc_info=True)
            return False, False  # U slučaju greške, pretpostavljamo da ne može i ne mora
    
    @track_execution_time
    def validate_move(self, card, hand, trick, trump_suit):
        """
        Provjerava je li potez valjan prema pravilima igre.
        
        Args:
            card (Card): Karta koju igrač želi odigrati
            hand (list): Lista karata u ruci igrača
            trick (list): Lista već odigranih karata u trenutnom štihu
            trump_suit (str): Adutska boja
            
        Returns:
            tuple: (bool, str) - (je li potez valjan, razlog ako nije)
            
        Raises:
            ValueError: Ako su parametri nevažeći
        """
        try:
            # Validacija parametara
            if not hand:
                error_msg = "Ruka je prazna"
                logger.warning(error_msg)
                return False, error_msg
                
            # Provjera je li karta u ruci igrača
            if card not in hand:
                error_msg = "Karta nije u ruci igrača"
                logger.debug(error_msg)
                return False, error_msg
            
            # Ako je prvi potez u štihu, bilo koja karta je dozvoljena
            if not trick:
                logger.debug(f"Prvi potez u štihu, karta {card} je valjana")
                return True, ""
            
            # Dohvati boju prve karte (tražena boja)
            lead_card = trick[0]
            if not hasattr(lead_card, 'suit'):
                error_msg = f"Prva karta u štihu nema svojstvo 'suit': {lead_card}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
                
            lead_suit = lead_card.suit
            
            # Provjeri ima li igrač traženu boju
            has_lead_suit = any(c.suit == lead_suit for c in hand)
            
            # Ako igrač ima traženu boju, mora ju igrati
            if has_lead_suit and card.suit != lead_suit:
                error_msg = f"Moraš igrati kartu boje {self._suit_name(lead_suit)}"
                logger.debug(error_msg)
                return False, error_msg
            
            # Provjeri mora li igrač igrati jaču kartu (über)
            if has_lead_suit and card.suit == lead_suit:
                # Provjera pravila übera korištenjem Rules klase
                if self.rules.must_play_higher_card(card, hand, trick, trump_suit):
                    try:
                        # Provjera je li karta dovoljno jaka
                        highest_card = max(
                            [c for c in trick if c.suit == lead_suit],
                            key=lambda c: self.rules.get_card_value_in_trick(c, lead_suit, trump_suit)
                        )
                        
                        card_value = self.rules.get_card_value_in_trick(card, lead_suit, trump_suit)
                        highest_value = self.rules.get_card_value_in_trick(highest_card, lead_suit, trump_suit)
                        
                        if card_value < highest_value:
                            error_msg = f"Moraš igrati viši {self._suit_name(lead_suit)} ako ga imaš"
                            logger.debug(error_msg)
                            return False, error_msg
                    except Exception as e:
                        logger.error(f"Greška pri provjeri übera: {str(e)}", exc_info=True)
            
            # Provjeri adutsko pravilo ako igrač nema traženu boju
            if not has_lead_suit:
                # Normalizacija adutske boje
                trump_suit_code = self._normalize_suit(trump_suit)
                
                # Provjeri je li adut već igran
                adut_played = any(c.suit == trump_suit_code for c in trick)
                
                # Provjeri ima li igrač aduta
                has_trump = any(c.suit == trump_suit_code for c in hand)
                
                # Ako adut nije igran i igrač ima aduta, mora ga igrati
                if not adut_played and has_trump and card.suit != trump_suit_code:
                    error_msg = f"Moraš igrati aduta ({self._suit_name(trump_suit_code)}) ako nemaš traženu boju"
                    logger.debug(error_msg)
                    return False, error_msg
            
            # Potez je valjan
            logger.debug(f"Potez s kartom {card} je valjan")
            return True, ""
        except Exception as e:
            logger.error(f"Greška pri validaciji poteza: {str(e)}", exc_info=True)
            return False, f"Greška pri validaciji: {str(e)}"
    
    @track_execution_time
    def validate_first_card(self, card, hand):
        """
        Provjerava valjanost prve karte u štihu.
        
        Args:
            card (Card): Karta koju igrač želi odigrati
            hand (list): Lista karata u ruci igrača
            
        Returns:
            tuple: (bool, str) - (je li potez valjan, razlog ako nije)
            
        Raises:
            ValueError: Ako su parametri nevažeći
        """
        try:
            # Validacija parametara
            if not isinstance(hand, list):
                error_msg = f"Parametar hand mora biti lista, a dobiven je {type(hand)}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
                
            if not hand:
                error_msg = "Ruka je prazna"
                logger.warning(error_msg)
                return False, error_msg
            
            # Prva karta u štihu može biti bilo koja karta iz ruke
            if card not in hand:
                error_msg = f"Karta {card} nije u ruci igrača"
                logger.debug(error_msg)
                return False, error_msg
            
            logger.debug(f"Prva karta {card} je valjana")
            return True, ""
        except Exception as e:
            logger.error(f"Greška pri validaciji prve karte: {str(e)}", exc_info=True)
            return False, f"Greška pri validaciji: {str(e)}"
    
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
            return suit  # U slučaju greške, vraćamo izvornu vrijednost
    
    @lru_cache(maxsize=16)
    def _suit_name(self, suit_code):
        """
        Vraća čitljivo ime boje.
        
        Args:
            suit_code (str): Kod boje ('S', 'H', 'D', 'C')
            
        Returns:
            str: Čitljivo ime boje na hrvatskom
            
        Raises:
            ValueError: Ako je kod boje nevažeći
        """
        try:
            if not suit_code:
                return "nepoznato"
                
            name = self.SUIT_NAMES.get(suit_code, suit_code)
            return name
        except Exception as e:
            logger.error(f"Greška pri dohvatu imena boje: {str(e)}", exc_info=True)
            return str(suit_code)  # U slučaju greške, vraćamo kod kao string