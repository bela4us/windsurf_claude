"""
Modul koji definira pravila Belot igre.

Ovaj modul pruža implementaciju klase Rules koja sadrži sva pravila
potrebna za igranje Belot igre, uključujući pravila bacanja karata,
određivanje pobjednika štiha, i rangiranje karata.
"""

from game.game_logic.card import Card


class Rules:
    """
    Klasa koja definira pravila Belot igre.
    
    Sadrži metode za određivanje valjanosti poteza, jačine karata,
    pobjednika štiha, i druge elemente pravila Belot igre.
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
    
    def __init__(self):
        """Inicijalizira objekt pravila igre."""
        pass
    
    def get_card_value_in_trick(self, card, lead_suit, trump_suit):
        """
        Određuje jačinu karte u štihu.
        
        Args:
            card: Karta čija se jačina određuje
            lead_suit: Boja prve karte u štihu (tražena boja)
            trump_suit: Adutska boja
            
        Returns:
            int: Vrijednost koja predstavlja jačinu karte (veći broj = jača karta)
        """
        # Normalizacija boja iz punih imena u kodove
        trump_suit_code = self._normalize_suit(trump_suit)
        lead_suit_code = self._normalize_suit(lead_suit)
        
        # Ako je karta adut, određujemo njenu jačinu prema poretku aduta
        if card.suit == trump_suit_code:
            # Adut uvijek pobjedi ne-adut
            return 100 + self.TRUMP_ORDER.get(card.value, 0)
        
        # Ako karta prati traženu boju, rangiramo je prema ne-adutskom poretku
        if card.suit == lead_suit_code:
            return self.NON_TRUMP_ORDER.get(card.value, 0)
        
        # Ako karta ne prati traženu boju i nije adut, ima najnižu vrijednost
        return -1
    
    def is_card_playable(self, card, hand, trick, trump_suit):
        """
        Provjerava može li se karta odigrati prema pravilima igre.
        
        Args:
            card: Karta koju igrač želi odigrati
            hand: Lista karata u ruci igrača
            trick: Lista već odigranih karata u trenutnom štihu
            trump_suit: Adutska boja
            
        Returns:
            bool: True ako se karta može odigrati, False inače
        """
        # Ako je ruka prazna ili karta nije u ruci, ne može se odigrati
        if not hand or card not in hand:
            return False
        
        # Ako je prvi potez u štihu, može se odigrati bilo koja karta
        if not trick:
            return True
        
        # Prva karta u štihu određuje traženu boju
        lead_card = trick[0]
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
                return len(higher_cards) == 0 or card in higher_cards
            
            # Inače, može igrati bilo koju kartu tražene boje
            return card.suit == lead_suit
        
        # Ako nema traženu boju, provjeri je li netko već bacio aduta
        adut_played = any(c.suit == trump_suit_code for c in trick)
        
        # Ako adut nije igran i igrač ima aduta, mora ga baciti
        has_trump = any(c.suit == trump_suit_code for c in hand)
        if not adut_played and has_trump:
            return card.suit == trump_suit_code
        
        # Ako igrač nema ni traženu boju ni aduta, može igrati bilo koju kartu
        return True
    
    def must_play_higher_card(self, card, hand, trick, trump_suit):
        """
        Provjerava mora li igrač igrati višu kartu (übati) ako može.
        
        Prema pravilima Belota, igrač mora igrati višu kartu od najviše 
        karte u štihu ako ima traženu boju, osim ako je adut već igran.
        
        Args:
            card: Karta koju igrač želi odigrati
            hand: Lista karata u ruci igrača
            trick: Lista već odigranih karata u trenutnom štihu
            trump_suit: Adutska boja
            
        Returns:
            bool: True ako igrač mora igrati višu kartu, False inače
        """
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
    
    def determine_trick_winner(self, trick, trump_suit):
        """
        Određuje indeks pobjednika štiha.
        
        Args:
            trick: Lista karata u štihu
            trump_suit: Adutska boja
            
        Returns:
            int: Indeks pobjednika štiha (0-3)
        """
        # Normalizacija adutske boje
        trump_suit_code = self._normalize_suit(trump_suit)
        
        # Ako je štih prazan, nema pobjednika
        if not trick:
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
        
        return strongest_card_index
    
    def check_belot(self, hand, trump_suit):
        """
        Provjerava ima li igrač belot (kralj i dama u adutu).
        
        Args:
            hand: Lista karata u ruci igrača
            trump_suit: Adutska boja
            
        Returns:
            bool: True ako igrač ima belot, False inače
        """
        # Normalizacija adutske boje
        trump_suit_code = self._normalize_suit(trump_suit)
        
        # Pronađi sve karte aduta
        trump_cards = [card for card in hand if card.suit == trump_suit_code]
        
        # Provjeri ima li igrač kralja i damu u adutu
        has_king = any(card.value == 'K' for card in trump_cards)
        has_queen = any(card.value == 'Q' for card in trump_cards)
        
        return has_king and has_queen
    
    def check_declarations(self, hand, trump_suit=None):
        """
        Provjerava sva moguća zvanja u ruci igrača.
        
        Args:
            hand: Lista karata u ruci igrača
            trump_suit: Adutska boja (potrebno za belu)
            
        Returns:
            list: Lista zvanja s tipom i vrijednošću
        """
        declarations = []
        
        # Provjera bele (kralj i dama u adutu)
        if trump_suit and self.check_belot(hand, trump_suit):
            declarations.append({
                'type': 'bela',
                'value': self.DECLARATIONS['bela'],
                'cards': [card for card in hand if card.suit == self._normalize_suit(trump_suit) 
                         and card.value in ['K', 'Q']]
            })
        
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
        
        # Provjera belota (svih 8 karata iste boje)
        for suit, cards in suit_groups.items():
            if len(cards) == 8:
                declarations.append({
                    'type': 'belot',
                    'value': self.DECLARATIONS['belot'],
                    'cards': cards
                })
        
        return declarations
    
    def must_follow_suit(self, hand, lead_suit, trump_suit):
        """
        Vraća listu karata koje igrač može igrati poštujući boju.
        
        Args:
            hand: Lista karata u ruci igrača
            lead_suit: Tražena boja
            trump_suit: Adutska boja
            
        Returns:
            list: Lista karata koje igrač može odigrati
        """
        lead_suit_code = self._normalize_suit(lead_suit)
        trump_suit_code = self._normalize_suit(trump_suit)
        
        # Karte tražene boje
        lead_suit_cards = [card for card in hand if card.suit == lead_suit_code]
        
        # Ako igrač ima karte tražene boje, mora ih igrati
        if lead_suit_cards:
            return lead_suit_cards
        
        # Ako nema karte tražene boje, provjeri adutske karte
        trump_cards = [card for card in hand if card.suit == trump_suit_code]
        
        # Ako ima adute, mora igrati adute
        if trump_cards:
            return trump_cards
        
        # Ako nema ni traženu boju ni aduta, može igrati bilo koju kartu
        return hand
    
    def can_trump(self, hand, lead_suit, trump_suit, trick):
        """
        Provjerava može li igrač rezati adutom.
        
        Args:
            hand: Lista karata u ruci igrača
            lead_suit: Tražena boja
            trump_suit: Adutska boja
            trick: Karte već odigrane u štihu
            
        Returns:
            bool: True ako igrač može rezati, False inače
        """
        lead_suit_code = self._normalize_suit(lead_suit)
        trump_suit_code = self._normalize_suit(trump_suit)
        
        # Igrač mora imati aduta da bi mogao rezati
        has_trump = any(card.suit == trump_suit_code for card in hand)
        if not has_trump:
            return False
        
        # Igrač ne smije imati traženu boju
        has_lead_suit = any(card.suit == lead_suit_code for card in hand)
        if has_lead_suit:
            return False
        
        # Provjeri je li adut već igran u štihu
        adut_already_played = any(card.suit == trump_suit_code for card in trick)
        
        # Ako adut već postoji u štihu, igrač nije obavezan rezati
        # Ali svejedno može rezati višim adutom
        return not adut_already_played
    
    def validate_move(self, card, hand, trick, trump_suit):
        """
        Provjerava je li potez valjan prema pravilima igre.
        
        Args:
            card: Karta koju igrač želi odigrati
            hand: Lista karata u ruci igrača
            trick: Lista već odigranih karata u trenutnom štihu
            trump_suit: Adutska boja
            
        Returns:
            bool: True ako je potez valjan, False inače
        """
        return self.is_card_playable(card, hand, trick, trump_suit)
    
    def validate_bid(self, player_index, trick_number, suit):
        """
        Provjerava je li zvanje aduta valjano.
        
        Args:
            player_index: Indeks igrača koji zove aduta
            trick_number: Broj štiha
            suit: Boja za aduta
            
        Returns:
            bool: True ako je zvanje valjano, False inače
        """
        # Provjeri je li boja valjana
        if suit not in ['S', 'H', 'D', 'C', 'spades', 'hearts', 'diamonds', 'clubs']:
            return False
        
        # U prvom štihu svaki igrač može zvati aduta
        if trick_number == 0:
            return True
        
        # U ostalim štihovima samo određeni igrači mogu zvati aduta (ovisi o implementaciji)
        # Ovo je pojednostavljeno pravilo
        return True
    
    def _find_longest_sequence(self, sorted_cards):
        """
        Pronalazi najdulji niz u sortiranoj listi karata.
        
        Args:
            sorted_cards: Sortirana lista karata iste boje
            
        Returns:
            list: Najdulji niz karata ili None ako nema niza
        """
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
    
    def _normalize_suit(self, suit):
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
        return suit_map.get(suit.lower(), suit)