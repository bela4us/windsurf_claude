"""
Modul koji definira pravila Belot igre.

Ovaj modul pruža implementaciju klase Rules koja sadrži sva pravila
potrebna za igranje Belot igre, uključujući pravila bacanja karata,
određivanje pobjednika štiha, i rangiranje karata.
"""

import logging
from functools import lru_cache
from game.game_logic.card import Card
from utils.decorators import track_execution_time

# Konfiguracija loggera
logger = logging.getLogger(__name__)

class Rules:
    """
    Klasa koja definira pravila Belot igre.
    
    Sadrži metode za određivanje valjanosti poteza, jačine karata,
    pobjednika štiha, i druge elemente pravila Belot igre.
    
    Attributes:
        NON_TRUMP_ORDER (dict): Redoslijed jačine karata kada boja NIJE adut
        TRUMP_ORDER (dict): Redoslijed jačine karata kada je boja adut
        DECLARATIONS (dict): Tipovi i vrijednosti zvanja
        _cache_timestamp (float): Vremenska oznaka za invalidaciju keša
    """
    
    # Redoslijed jačine karata kada boja NIJE adut (od najslabije do najjače)
    NON_TRUMP_ORDER = {'7': 0, '8': 1, '9': 2, 'J': 3, 'Q': 4, 'K': 5, '10': 6, 'A': 7}
    
    # Redoslijed jačine karata kada je boja adut (od najslabije do najjače)
    TRUMP_ORDER = {'7': 0, '8': 1, 'Q': 2, 'K': 3, '10': 4, 'A': 5, '9': 6, 'J': 7}
    
    # Tipovi i vrijednosti zvanja
    DECLARATIONS = {
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
    
    # Mapiranje punih imena boja na kodove (za normalizaciju)
    SUIT_MAP = {
        'spades': 'S',
        'hearts': 'H',
        'diamonds': 'D',
        'clubs': 'C'
    }
    
    @track_execution_time
    def __init__(self):
        """Inicijalizira objekt pravila igre."""
        self._cache_timestamp = 0.0
        logger.debug("Inicijalizirani objekt pravila igre")
    
    def _invalidate_cache(self):
        """Invalidira sve kešove povezane s objektom pravila."""
        import time
        self._cache_timestamp = time.time()
        # Briše sve keširane vrijednosti pozivanjem odgovarajućih clear metoda
        self.get_card_value_in_trick.cache_clear()
        self._normalize_suit.cache_clear()
        logger.debug("Keš pravila igre invalidiran")
    
    @track_execution_time
    @lru_cache(maxsize=128)
    def get_card_value_in_trick(self, card, lead_suit, trump_suit):
        """
        Određuje jačinu karte u štihu.
        
        Args:
            card (Card): Karta čija se jačina određuje
            lead_suit (str): Boja prve karte u štihu (tražena boja)
            trump_suit (str): Adutska boja
            
        Returns:
            int: Vrijednost koja predstavlja jačinu karte (veći broj = jača karta)
            
        Raises:
            ValueError: Ako je karta nevažeća
        """
        try:
            # Normalizacija boja iz punih imena u kodove
            trump_suit_code = self._normalize_suit(trump_suit)
            lead_suit_code = self._normalize_suit(lead_suit)
            
            # Validacija karte
            if not hasattr(card, 'suit') or not hasattr(card, 'value'):
                error_msg = f"Nevažeća karta: {card}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # Ako je karta adut, određujemo njenu jačinu prema poretku aduta
            if card.suit == trump_suit_code:
                # Adut uvijek pobjedi ne-adut
                return 100 + self.TRUMP_ORDER.get(card.value, 0)
            
            # Ako karta prati traženu boju, rangiramo je prema ne-adutskom poretku
            if card.suit == lead_suit_code:
                return self.NON_TRUMP_ORDER.get(card.value, 0)
            
            # Ako karta ne prati traženu boju i nije adut, ima najnižu vrijednost
            return -1
        except Exception as e:
            logger.error(f"Greška pri određivanju jačine karte: {str(e)}", exc_info=True)
            # U slučaju greške, vrati negativnu vrijednost
            return -100
    
    @track_execution_time
    def is_card_playable(self, card, hand, trick, trump_suit):
        """
        Provjerava može li se karta odigrati prema pravilima igre.
        
        Args:
            card (Card): Karta koju igrač želi odigrati
            hand (list): Lista karata u ruci igrača
            trick (list): Lista već odigranih karata u trenutnom štihu
            trump_suit (str): Adutska boja
            
        Returns:
            bool: True ako se karta može odigrati, False inače
            
        Raises:
            ValueError: Ako je karta nevažeća ili ako su drugi parametri nevažeći
        """
        try:
            # Validacija parametara
            if not hand:
                logger.debug("Ruka je prazna, karta se ne može odigrati")
                return False
            
            if card not in hand:
                logger.debug(f"Karta {card} nije u ruci, ne može se odigrati")
                return False
            
            # Ako je prvi potez u štihu, može se odigrati bilo koja karta
            if not trick:
                return True
            
            # Prva karta u štihu određuje traženu boju
            lead_card = trick[0]
            if not hasattr(lead_card, 'suit'):
                error_msg = f"Prva karta u štihu nema svojstvo 'suit': {lead_card}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
                
            lead_suit = lead_card.suit
            
            # Normalizacija adutske boje
            trump_suit_code = self._normalize_suit(trump_suit)
            
            # Praćenje boje - ako igrač ima kartu tražene boje, mora je igrati
            has_lead_suit = any(c.suit == lead_suit for c in hand)
            if has_lead_suit:
                # Provjera mora li igrati jaču kartu (übati) ako može
                if card.suit == lead_suit and self.must_play_higher_card(card, hand, trick, trump_suit):
                    higher_cards = [c for c in hand if c.suit == lead_suit and 
                                self.get_card_value_in_trick(c, lead_suit, trump_suit) >
                                self.get_card_value_in_trick(lead_card, lead_suit, trump_suit)]
                    valid_move = len(higher_cards) == 0 or card in higher_cards
                    if not valid_move:
                        logger.debug(f"Igrač mora odigrati jaču kartu od {lead_card} ako može")
                    return valid_move
                
                # Inače, može igrati bilo koju kartu tražene boje
                valid_move = card.suit == lead_suit
                if not valid_move:
                    logger.debug(f"Igrač mora pratiti boju {lead_suit}, ali je pokušao odigrati kartu boje {card.suit}")
                return valid_move
            
            # Ako nema traženu boju, provjeri je li netko već bacio aduta
            adut_played = any(c.suit == trump_suit_code for c in trick)
            
            # Ako adut nije igran i igrač ima aduta, mora ga baciti
            has_trump = any(c.suit == trump_suit_code for c in hand)
            if not adut_played and has_trump:
                valid_move = card.suit == trump_suit_code
                if not valid_move:
                    logger.debug(f"Igrač mora odigrati aduta {trump_suit_code}, ali je pokušao odigrati kartu boje {card.suit}")
                return valid_move
            
            # Ako igrač nema ni traženu boju ni aduta, može igrati bilo koju kartu
            return True
        except Exception as e:
            logger.error(f"Greška pri provjeri može li se karta odigrati: {str(e)}", exc_info=True)
            return False
    
    @track_execution_time
    def must_play_higher_card(self, card, hand, trick, trump_suit):
        """
        Provjerava mora li igrač igrati višu kartu (übati) ako može.
        
        Prema pravilima Belota, igrač mora igrati višu kartu od najviše 
        karte u štihu ako ima traženu boju, osim ako je adut već igran.
        
        Args:
            card (Card): Karta koju igrač želi odigrati
            hand (list): Lista karata u ruci igrača
            trick (list): Lista već odigranih karata u trenutnom štihu
            trump_suit (str): Adutska boja
            
        Returns:
            bool: True ako igrač mora igrati višu kartu, False inače
            
        Raises:
            ValueError: Ako su parametri nevažeći
        """
        try:
            # Ako je prvi potez u štihu, nema potrebe za übati
            if not trick:
                return False
            
            # Prva karta u štihu određuje traženu boju
            lead_card = trick[0]
            lead_suit = lead_card.suit
            
            # Normalizacija adutske boje
            trump_suit_code = self._normalize_suit(trump_suit)
            
            # Provjeri je li adut već igran
            adut_played = any(c.suit == trump_suit_code for c in trick)
            if adut_played:
                return False  # Ako je adut već igran, ne mora übati
            
            # Pronađi najvišu kartu tražene boje u štihu
            same_suit_cards = [c for c in trick if c.suit == lead_suit]
            if not same_suit_cards:
                return False  # Ako nema karata tražene boje, ne mora übati
            
            highest_card = max(same_suit_cards, 
                            key=lambda c: self.get_card_value_in_trick(c, lead_suit, trump_suit))
            
            # Ako je karta koju igrač želi odigrati tražene boje ali slabija od najviše,
            # igrač mora igrati jaču kartu ako je ima
            if (card.suit == lead_suit and 
                self.get_card_value_in_trick(card, lead_suit, trump_suit) < 
                self.get_card_value_in_trick(highest_card, lead_suit, trump_suit)):
                
                # Provjeri ima li igrač jaču kartu od najviše u štihu
                has_higher_card = any(c.suit == lead_suit and 
                                    self.get_card_value_in_trick(c, lead_suit, trump_suit) > 
                                    self.get_card_value_in_trick(highest_card, lead_suit, trump_suit) 
                                    for c in hand)
                
                return has_higher_card
            
            return False
        except Exception as e:
            logger.error(f"Greška pri provjeri mora li igrač igrati višu kartu: {str(e)}", exc_info=True)
            return False
    
    @track_execution_time
    def determine_trick_winner(self, trick, trump_suit):
        """
        Određuje indeks pobjednika štiha.
        
        Args:
            trick (list): Lista karata u štihu
            trump_suit (str): Adutska boja
            
        Returns:
            int: Indeks pobjednika štiha (0-3)
            
        Raises:
            ValueError: Ako je štih prazan ili ako su parametri nevažeći
        """
        try:
            # Normalizacija adutske boje
            trump_suit_code = self._normalize_suit(trump_suit)
            
            # Ako je štih prazan, nema pobjednika
            if not trick:
                logger.warning("Štih je prazan, nema pobjednika")
                return -1
            
            # Prva karta u štihu određuje traženu boju
            lead_card = trick[0]
            lead_suit = lead_card.suit
            
            # Inicijalno, najjača karta je prva
            strongest_card_index = 0
            strongest_card_value = self.get_card_value_in_trick(lead_card, lead_suit, trump_suit_code)
            
            # Prolazak kroz sve karte u štihu i određivanje najjače
            for i, card in enumerate(trick[1:], 1):
                card_value = self.get_card_value_in_trick(card, lead_suit, trump_suit_code)
                
                # Ako je ova karta jača od trenutno najjače, ažuriraj rezultat
                if card_value > strongest_card_value:
                    strongest_card_index = i
                    strongest_card_value = card_value
            
            logger.debug(f"Pobjednik štiha je igrač s indeksom {strongest_card_index}")
            return strongest_card_index
        except Exception as e:
            logger.error(f"Greška pri određivanju pobjednika štiha: {str(e)}", exc_info=True)
            return -1  # U slučaju greške, vrati nevažeći indeks
    
    @track_execution_time
    def check_belot(self, hand, trump_suit):
        """
        Provjerava ima li igrač belot (kralj i dama u adutu).
        
        Args:
            hand (list): Lista karata u ruci igrača
            trump_suit (str): Adutska boja
            
        Returns:
            bool: True ako igrač ima belot, False inače
            
        Raises:
            ValueError: Ako je ruka prazna ili adutska boja nevažeća
        """
        try:
            # Normalizacija adutske boje
            trump_suit_code = self._normalize_suit(trump_suit)
            
            # Validacija
            if not hand:
                logger.debug("Ruka je prazna, nema belota")
                return False
                
            if not trump_suit_code or trump_suit_code not in Card.VALID_SUITS:
                logger.warning(f"Nevažeća adutska boja: {trump_suit}")
                return False
            
            # Pronađi sve karte aduta
            trump_cards = [card for card in hand if card.suit == trump_suit_code]
            
            # Provjeri ima li igrač kralja i damu u adutu
            has_king = any(card.value == 'K' for card in trump_cards)
            has_queen = any(card.value == 'Q' for card in trump_cards)
            
            if has_king and has_queen:
                logger.debug(f"Pronađen belot u boji {trump_suit_code}")
                return True
                
            return False
        except Exception as e:
            logger.error(f"Greška pri provjeri belota: {str(e)}", exc_info=True)
            return False
    
    @track_execution_time
    def check_declarations(self, hand, trump_suit=None):
        """
        Provjerava sva moguća zvanja u ruci igrača.
        
        Args:
            hand (list): Lista karata u ruci igrača
            trump_suit (str, optional): Adutska boja (potrebno za belu)
            
        Returns:
            list: Lista zvanja s tipom i vrijednošću
            
        Raises:
            ValueError: Ako je ruka prazna ili sadrži nevažeće karte
        """
        try:
            declarations = []
            
            # Validacija
            if not hand:
                logger.debug("Ruka je prazna, nema zvanja")
                return declarations
            
            # Provjera bele (kralj i dama u adutu)
            if trump_suit and self.check_belot(hand, trump_suit):
                trump_suit_code = self._normalize_suit(trump_suit)
                declarations.append({
                    'type': 'bela',
                    'value': self.DECLARATIONS['bela'],
                    'cards': [card for card in hand if card.suit == trump_suit_code 
                            and card.value in ['K', 'Q']]
                })
                logger.debug(f"Pronađen belot u boji {trump_suit}")
            
            # Provjera četiri iste karte
            value_groups = {}
            for card in hand:
                if card.value not in value_groups:
                    value_groups[card.value] = []
                value_groups[card.value].append(card)
            
            four_of_kind_map = {
                'J': 'four_jacks',
                '9': 'four_nines',
                'A': 'four_aces',
                '10': 'four_tens',
                'K': 'four_kings',
                'Q': 'four_queens'
            }
            
            for value, cards in value_groups.items():
                if len(cards) == 4 and value in four_of_kind_map:
                    declaration_type = four_of_kind_map[value]
                    declarations.append({
                        'type': declaration_type,
                        'value': self.DECLARATIONS[declaration_type],
                        'cards': cards
                    })
                    logger.debug(f"Pronađeno četiri {value}")
            
            # Provjera nizova u istoj boji
            suit_groups = {}
            for card in hand:
                if card.suit not in suit_groups:
                    suit_groups[card.suit] = []
                suit_groups[card.suit].append(card)
            
            for suit, cards in suit_groups.items():
                # Sortiraj karte prema redoslijedu u špilu
                sorted_cards = sorted(cards, key=lambda c: self.NON_TRUMP_ORDER.get(c.value, 0))
                
                # Traži najduže nizove
                longest_sequence = self._find_longest_sequence(sorted_cards)
                if longest_sequence:
                    if len(longest_sequence) >= 5:
                        declaration_type = 'sequence_5_plus'
                    elif len(longest_sequence) == 4:
                        declaration_type = 'sequence_4'
                    elif len(longest_sequence) == 3:
                        declaration_type = 'sequence_3'
                    else:
                        continue  # Prekratki niz
                    
                    declarations.append({
                        'type': declaration_type,
                        'value': self.DECLARATIONS[declaration_type],
                        'cards': longest_sequence
                    })
                    logger.debug(f"Pronađen niz od {len(longest_sequence)} karata u boji {suit}")
            
            # Provjera belota (svih 8 karata iste boje)
            for suit, cards in suit_groups.items():
                if len(cards) == 8:
                    declarations.append({
                        'type': 'belot',
                        'value': self.DECLARATIONS['belot'],
                        'cards': cards
                    })
                    logger.debug(f"Pronađen belot (8 karata) u boji {suit}")
            
            return declarations
        except Exception as e:
            logger.error(f"Greška pri provjeri zvanja: {str(e)}", exc_info=True)
            return []
    
    @track_execution_time
    def must_follow_suit(self, hand, lead_suit, trump_suit):
        """
        Vraća listu karata koje igrač može igrati poštujući boju.
        
        Args:
            hand (list): Lista karata u ruci igrača
            lead_suit (str): Tražena boja
            trump_suit (str): Adutska boja
            
        Returns:
            list: Lista karata koje igrač može odigrati
            
        Raises:
            ValueError: Ako su parametri nevažeći
        """
        try:
            # Validacija
            if not hand:
                logger.debug("Ruka je prazna")
                return []
                
            lead_suit_code = self._normalize_suit(lead_suit)
            trump_suit_code = self._normalize_suit(trump_suit)
            
            # Karte tražene boje
            lead_suit_cards = [card for card in hand if card.suit == lead_suit_code]
            
            # Ako igrač ima karte tražene boje, mora ih igrati
            if lead_suit_cards:
                logger.debug(f"Igrač mora pratiti boju {lead_suit_code}, pronađeno {len(lead_suit_cards)} odgovarajućih karata")
                return lead_suit_cards
            
            # Ako nema karte tražene boje, provjeri adutske karte
            trump_cards = [card for card in hand if card.suit == trump_suit_code]
            
            # Ako ima adute, mora igrati adute
            if trump_cards:
                logger.debug(f"Igrač nema boju {lead_suit_code}, ali ima {len(trump_cards)} aduta {trump_suit_code}")
                return trump_cards
            
            # Ako nema ni traženu boju ni aduta, može igrati bilo koju kartu
            logger.debug(f"Igrač nema ni boju {lead_suit_code} ni aduta {trump_suit_code}, može igrati bilo koju kartu")
            return hand
        except Exception as e:
            logger.error(f"Greška pri određivanju karata koje igrač može odigrati: {str(e)}", exc_info=True)
            return hand  # U slučaju greške, vrati sve karte kao opciju
    
    @track_execution_time
    def can_trump(self, hand, lead_suit, trump_suit, trick):
        """
        Provjerava može li igrač rezati adutom.
        
        Args:
            hand (list): Lista karata u ruci igrača
            lead_suit (str): Tražena boja
            trump_suit (str): Adutska boja
            trick (list): Karte već odigrane u štihu
            
        Returns:
            bool: True ako igrač može rezati, False inače
            
        Raises:
            ValueError: Ako su parametri nevažeći
        """
        try:
            # Validacija
            if not hand or not trick:
                return False
                
            lead_suit_code = self._normalize_suit(lead_suit)
            trump_suit_code = self._normalize_suit(trump_suit)
            
            # Igrač mora imati aduta da bi mogao rezati
            has_trump = any(card.suit == trump_suit_code for card in hand)
            if not has_trump:
                logger.debug("Igrač nema aduta, ne može rezati")
                return False
            
            # Igrač ne smije imati traženu boju
            has_lead_suit = any(card.suit == lead_suit_code for card in hand)
            if has_lead_suit:
                logger.debug("Igrač ima traženu boju, ne može rezati")
                return False
            
            # Provjeri je li adut već igran u štihu
            adut_already_played = any(card.suit == trump_suit_code for card in trick)
            
            if adut_already_played:
                logger.debug("Adut je već igran u štihu, igrač nije obvezan rezati")
            else:
                logger.debug("Adut nije igran u štihu, igrač mora rezati")
            
            # Ako adut već postoji u štihu, igrač nije obavezan rezati
            # Ali svejedno može rezati višim adutom
            return not adut_already_played
        except Exception as e:
            logger.error(f"Greška pri provjeri može li igrač rezati adutom: {str(e)}", exc_info=True)
            return False
    
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
            bool: True ako je potez valjan, False inače
            
        Raises:
            ValueError: Ako su parametri nevažeći
        """
        try:
            valid = self.is_card_playable(card, hand, trick, trump_suit)
            if valid:
                logger.debug(f"Potez je valjan: {card}")
            else:
                logger.debug(f"Potez nije valjan: {card}")
            return valid
        except Exception as e:
            logger.error(f"Greška pri validaciji poteza: {str(e)}", exc_info=True)
            return False
    
    @track_execution_time
    def validate_bid(self, player_index, trick_number, suit):
        """
        Provjerava je li zvanje aduta valjano.
        
        Args:
            player_index (int): Indeks igrača koji zove aduta
            trick_number (int): Broj štiha
            suit (str): Boja za aduta
            
        Returns:
            bool: True ako je zvanje valjano, False inače
            
        Raises:
            ValueError: Ako su parametri nevažeći
        """
        try:
            # Validacija
            if player_index < 0 or player_index > 3:
                error_msg = f"Nevažeći indeks igrača: {player_index}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
                
            if trick_number < 0:
                error_msg = f"Nevažeći broj štiha: {trick_number}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
                
            # Provjeri je li boja valjana
            normalized_suit = self._normalize_suit(suit)
            if normalized_suit not in Card.VALID_SUITS:
                error_msg = f"Nevažeća boja za aduta: {suit}"
                logger.warning(error_msg)
                return False
            
            # U prvom štihu svaki igrač može zvati aduta
            if trick_number == 0:
                logger.debug(f"Zvanje aduta {suit} u prvom štihu je valjano za igrača {player_index}")
                return True
            
            # U ostalim štihovima samo određeni igrači mogu zvati aduta (ovisi o implementaciji)
            # Ovo je pojednostavljeno pravilo
            logger.debug(f"Zvanje aduta {suit} u štihu {trick_number} je valjano za igrača {player_index}")
            return True
        except Exception as e:
            logger.error(f"Greška pri validaciji zvanja aduta: {str(e)}", exc_info=True)
            return False
    
    def _find_longest_sequence(self, sorted_cards):
        """
        Pronalazi najdulji niz u sortiranoj listi karata.
        
        Args:
            sorted_cards (list): Sortirana lista karata iste boje
            
        Returns:
            list: Najdulji niz karata ili None ako nema niza
            
        Raises:
            ValueError: Ako su parametri nevažeći
        """
        try:
            if not sorted_cards:
                return None
            
            # Pretvori vrijednosti karata u indekse prema standardnom redoslijedu
            value_indices = [self.NON_TRUMP_ORDER.get(card.value, 0) for card in sorted_cards]
            
            # Traži najdulji uzastopni niz
            longest_sequence = []
            current_sequence = [sorted_cards[0]]
            
            for i in range(1, len(sorted_cards)):
                if value_indices[i] == value_indices[i-1] + 1:
                    current_sequence.append(sorted_cards[i])
                else:
                    if len(current_sequence) >= 3 and len(current_sequence) > len(longest_sequence):
                        longest_sequence = current_sequence.copy()
                    current_sequence = [sorted_cards[i]]
            
            # Provjeri zadnju sekvencu
            if len(current_sequence) >= 3 and len(current_sequence) > len(longest_sequence):
                longest_sequence = current_sequence
            
            return longest_sequence if len(longest_sequence) >= 3 else None
        except Exception as e:
            logger.error(f"Greška pri traženju najduljeg niza karata: {str(e)}", exc_info=True)
            return None
    
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