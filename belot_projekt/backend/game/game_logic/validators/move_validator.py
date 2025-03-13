"""
Modul koji definira validator poteza u Belot igri.

Ovaj modul pruža implementaciju klase MoveValidator koja je odgovorna za
provjeru valjanosti poteza (igranja karata) prema pravilima Belot igre.
Validator osigurava da igrači poštuju pravila o praćenju boje, bacanju aduta
i igranju jačih karata kada je to potrebno.
"""

from game.game_logic.card import Card
from game.game_logic.rules import Rules


class MoveValidator:
    """
    Klasa koja validira poteze u Belot igri.
    
    Provjerava jesu li potezi (igranje karata) valjani prema pravilima
    Belota, uključujući praćenje boje, bacanje aduta, i pravilo 'übera'.
    """
    
    def __init__(self):
        """Inicijalizira validator poteza."""
        self.rules = Rules()  # Koristimo Rules klasu za provjeru pravila
    
    def validate(self, card, hand, trick, trump_suit):
        """
        Glavna metoda validacije poteza (alias za validate_move).
        
        Args:
            card: Karta koju igrač želi odigrati
            hand: Lista karata u ruci igrača
            trick: Lista već odigranih karata u trenutnom štihu
            trump_suit: Adutska boja
            
        Returns:
            tuple: (bool, str) - (je li potez valjan, razlog ako nije)
        """
        return self.validate_move(card, hand, trick, trump_suit)
    
    def can_play_card(self, card, hand, trick, trump_suit):
        """
        Provjerava može li se karta odigrati prema pravilima.
        
        Args:
            card: Karta koju igrač želi odigrati
            hand: Lista karata u ruci igrača
            trick: Lista već odigranih karata u trenutnom štihu
            trump_suit: Adutska boja
            
        Returns:
            bool: True ako se karta može odigrati, False inače
        """
        valid, _ = self.validate_move(card, hand, trick, trump_suit)
        return valid
    
    def must_follow_suit(self, hand, lead_suit, trump_suit):
        """
        Vraća karte koje igrač može igrati poštujući pravilo praćenja boje.
        
        Args:
            hand: Lista karata u ruci igrača
            lead_suit: Tražena boja (boja prve karte u štihu)
            trump_suit: Adutska boja
            
        Returns:
            list: Lista karata koje igrač može odigrati
        """
        # Normalizacija boja
        lead_suit_code = self._normalize_suit(lead_suit)
        trump_suit_code = self._normalize_suit(trump_suit)
        
        # Provjeri ima li igrač karte tražene boje
        lead_suit_cards = [card for card in hand if card.suit == lead_suit_code]
        if lead_suit_cards:
            return lead_suit_cards
        
        # Ako nema karte tražene boje, treba igrati aduta ako ga ima
        trump_cards = [card for card in hand if card.suit == trump_suit_code]
        if trump_cards:
            return trump_cards
        
        # Ako nema ni traženu boju ni aduta, može baciti bilo koju kartu
        return hand
    
    def can_trump(self, hand, lead_suit, trump_suit, trick=None):
        """
        Provjerava može li i mora li igrač igrati aduta.
        
        Args:
            hand: Lista karata u ruci igrača
            lead_suit: Tražena boja (boja prve karte u štihu)
            trump_suit: Adutska boja
            trick: Lista karata već odigranih u štihu (opcionalno)
            
        Returns:
            tuple: (bool, bool) - (može li rezati, mora li rezati)
        """
        # Normalizacija boja
        lead_suit_code = self._normalize_suit(lead_suit)
        trump_suit_code = self._normalize_suit(trump_suit)
        
        # Provjeri ima li igrač karte tražene boje
        has_lead_suit = any(card.suit == lead_suit_code for card in hand)
        
        # Ako ima traženu boju, ne smije rezati
        if has_lead_suit:
            return False, False
            
        # Provjeri ima li aduta
        has_trump = any(card.suit == trump_suit_code for card in hand)
        if not has_trump:
            return False, False
            
        # Ako nema traženu boju ali ima aduta, ovisi je li adut već igran
        if trick:
            # Provjeri je li adut već igran
            adut_already_played = any(card.suit == trump_suit_code for card in trick)
            if adut_already_played:
                # Ako je adut već igran, može, ali ne mora rezati
                return True, False
                
        # Ako nema traženu boju i ima aduta i adut nije igran, mora rezati
        return True, True
    
    def validate_move(self, card, hand, trick, trump_suit):
        """
        Provjerava je li potez valjan prema pravilima igre.
        
        Args:
            card: Karta koju igrač želi odigrati
            hand: Lista karata u ruci igrača
            trick: Lista već odigranih karata u trenutnom štihu
            trump_suit: Adutska boja
            
        Returns:
            tuple: (bool, str) - (je li potez valjan, razlog ako nije)
        """
        # Provjera je li karta u ruci igrača
        if card not in hand:
            return False, "Karta nije u ruci igrača"
        
        # Ako je prvi potez u štihu, bilo koja karta je dozvoljena
        if not trick:
            return True, ""
        
        # Dohvati boju prve karte (tražena boja)
        lead_card = trick[0]
        lead_suit = lead_card.suit
        
        # Provjeri ima li igrač traženu boju
        has_lead_suit = any(c.suit == lead_suit for c in hand)
        
        # Ako igrač ima traženu boju, mora ju igrati
        if has_lead_suit and card.suit != lead_suit:
            return False, f"Moraš igrati kartu boje {self._suit_name(lead_suit)}"
        
        # Provjeri mora li igrač igrati jaču kartu (über)
        if has_lead_suit and card.suit == lead_suit:
            # Provjera pravila übera korištenjem Rules klase
            if self.rules.must_play_higher_card(card, hand, trick, trump_suit):
                # Provjera je li karta dovoljno jaka
                highest_card = max(
                    [c for c in trick if c.suit == lead_suit],
                    key=lambda c: self.rules.get_card_value_in_trick(c, lead_suit, trump_suit)
                )
                
                card_value = self.rules.get_card_value_in_trick(card, lead_suit, trump_suit)
                highest_value = self.rules.get_card_value_in_trick(highest_card, lead_suit, trump_suit)
                
                if card_value < highest_value:
                    return False, f"Moraš igrati viši {self._suit_name(lead_suit)} ako ga imaš"
        
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
                return False, f"Moraš igrati aduta ({self._suit_name(trump_suit_code)}) ako nemaš traženu boju"
        
        # Potez je valjan
        return True, ""
    
    def validate_first_card(self, card, hand):
        """
        Provjerava valjanost prve karte u štihu.
        
        Args:
            card: Karta koju igrač želi odigrati
            hand: Lista karata u ruci igrača
            
        Returns:
            tuple: (bool, str) - (je li potez valjan, razlog ako nije)
        """
        # Prva karta u štihu može biti bilo koja karta iz ruke
        if card not in hand:
            return False, "Karta nije u ruci igrača"
        
        return True, ""
    
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
    
    def _suit_name(self, suit_code):
        """
        Vraća čitljivo ime boje.
        
        Args:
            suit_code: Kod boje ('S', 'H', 'D', 'C')
            
        Returns:
            str: Čitljivo ime boje na hrvatskom
        """
        suit_names = {
            'S': 'pik',
            'H': 'herc',
            'D': 'karo',
            'C': 'tref'
        }
        return suit_names.get(suit_code, suit_code)