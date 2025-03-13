"""
Modul koji definira bodovanje u Belot igri.

Ovaj modul pruža implementaciju klase Scoring koja sadrži logiku za
izračun bodova u igri Belot, uključujući bodovanje karata, zvanja i štihova.
"""

from game.game_logic.card import Card


class Scoring:
    """
    Klasa koja definira bodovanje u Belot igri.
    
    Sadrži metode za izračun bodova za karte, štihove i zvanja.
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
    
    def __init__(self):
        """Inicijalizira objekt bodovanja igre."""
        pass
    
    def get_card_point_value(self, card, trump_suit):
        """
        Vraća bodovnu vrijednost karte.
        
        Args:
            card: Karta čija se vrijednost određuje
            trump_suit: Adutska boja
            
        Returns:
            int: Bodovna vrijednost karte
        """
        # Normalizacija trump_suit iz punog imena u kod
        trump_suit_code = self._normalize_suit(trump_suit)
        
        # Određivanje je li karta adut
        is_trump = (card.suit == trump_suit_code)
        
        # Odabir odgovarajućeg rječnika bodova
        points_dict = self.TRUMP_POINTS if is_trump else self.NON_TRUMP_POINTS
        
        # Dohvaćanje bodovne vrijednosti
        return points_dict.get(card.value, 0)
    
    def calculate_trick_points(self, trick, trump_suit, is_last_trick=False):
        """
        Izračunava ukupne bodove za štih.
        
        Args:
            trick: Lista poteza u štihu (lista Card objekata)
            trump_suit: Adutska boja
            is_last_trick: Je li ovo zadnji štih u rundi
            
        Returns:
            int: Ukupni bodovi za štih
        """
        # Normalizacija trump_suit iz punog imena u kod
        trump_suit_code = self._normalize_suit(trump_suit)
        
        # Izračunavanje bodova za karte u štihu
        points = sum(self.get_card_point_value(card, trump_suit_code) for card in trick)
        
        # Dodavanje bodova za zadnji štih
        if is_last_trick:
            points += self.LAST_TRICK_BONUS
        
        return points
    
    def calculate_declaration_points(self, declarations):
        """
        Izračunava ukupne bodove za zvanja.
        
        Args:
            declarations: Lista zvanja (rječnici s tipom i vrijednošću)
            
        Returns:
            int: Ukupni bodovi za zvanja
        """
        return sum(decl['value'] for decl in declarations)
    
    def add_last_trick_bonus(self, points):
        """
        Dodaje bonus bodove za zadnji štih.
        
        Args:
            points: Osnovni bodovi
            
        Returns:
            int: Bodovi s dodanim bonusom
        """
        return points + self.LAST_TRICK_BONUS
    
    def check_belot_bonus(self, hand, trump_suit):
        """
        Provjerava i vraća bodove za belot (kralj i dama u adutu).
        
        Args:
            hand: Lista karata u ruci igrača
            trump_suit: Adutska boja
            
        Returns:
            int: Bodovi za belot (20 ili 0)
        """
        trump_suit_code = self._normalize_suit(trump_suit)
        
        # Pronađi sve karte aduta
        trump_cards = [card for card in hand if card.suit == trump_suit_code]
        
        # Provjeri ima li igrač kralja i damu u adutu
        has_king = any(card.value == 'K' for card in trump_cards)
        has_queen = any(card.value == 'Q' for card in trump_cards)
        
        return self.DECLARATION_POINTS['bela'] if has_king and has_queen else 0
    
    def check_declarations_priority(self, team_a_declarations, team_b_declarations):
        """
        Određuje koji tim ima prioritet kod zvanja.
        
        Prema pravilima, ako oba tima imaju zvanja iste vrijednosti,
        prioritet ima tim koji je bliži djelitelju.
        
        Args:
            team_a_declarations: Lista zvanja tima A
            team_b_declarations: Lista zvanja tima B
            
        Returns:
            str: Tim s prioritetom ('a' ili 'b'), ili None ako su zvanja jednaka
        """
        # Pronađi najvišu vrijednost zvanja za svaki tim
        team_a_max = max([decl['value'] for decl in team_a_declarations], default=0)
        team_b_max = max([decl['value'] for decl in team_b_declarations], default=0)
        
        if team_a_max > team_b_max:
            return 'a'
        elif team_b_max > team_a_max:
            return 'b'
        elif team_a_max == team_b_max and team_a_max > 0:
            # Ako su zvanja jednake vrijednosti, potrebno je implementirati
            # logiku prioriteta prema blizini djelitelju (ovo ovisi o implementaciji igre)
            # Za sada vraćamo None (jednako)
            return None
        else:
            return None
    
    def calculate_round_score(self, team_a_tricks, team_b_tricks, team_a_declarations, team_b_declarations, calling_team):
        """
        Izračunava ukupne bodove za rundu.
        
        Args:
            team_a_tricks: Lista štihova tima A
            team_b_tricks: Lista štihova tima B
            team_a_declarations: Lista zvanja tima A
            team_b_declarations: Lista zvanja tima B
            calling_team: Tim koji je zvao aduta ('a' ili 'b')
            
        Returns:
            tuple: (bodovi_tim_a, bodovi_tim_b, pobjednički_tim)
        """
        # Izračunavanje bodova za štihove
        team_a_trick_points = sum(trick['points'] for trick in team_a_tricks)
        team_b_trick_points = sum(trick['points'] for trick in team_b_tricks)
        
        # Provjera štih-mača (štiglje)
        if not team_a_tricks:
            team_b_trick_points += self.CLEAN_SWEEP_BONUS
        elif not team_b_tricks:
            team_a_trick_points += self.CLEAN_SWEEP_BONUS
        
        # Izračunavanje bodova za zvanja
        team_a_declaration_points = sum(decl['value'] for decl in team_a_declarations)
        team_b_declaration_points = sum(decl['value'] for decl in team_b_declarations)
        
        # Bodovi s zvanjima
        team_a_points = team_a_trick_points + team_a_declaration_points
        team_b_points = team_b_trick_points + team_b_declaration_points
        
        # Primjena pravila "prolaza"
        if calling_team == 'a':
            if team_a_points <= team_b_points:
                # Tim A nije prošao, svi bodovi idu timu B
                team_b_points = team_a_points + team_b_points
                team_a_points = 0
                winner_team = 'b'
            else:
                winner_team = 'a'
        else:  # calling_team == 'b'
            if team_b_points <= team_a_points:
                # Tim B nije prošao, svi bodovi idu timu A
                team_a_points = team_a_points + team_b_points
                team_b_points = 0
                winner_team = 'a'
            else:
                winner_team = 'b'
        
        return team_a_points, team_b_points, winner_team
    
    def get_declaration_value(self, declaration_type, cards=None):
        """
        Vraća bodovnu vrijednost zvanja.
        
        Args:
            declaration_type: Tip zvanja (npr. 'sequence_3', 'four_jacks')
            cards: Lista karata koje čine zvanje (opcionalano)
            
        Returns:
            int: Bodovna vrijednost zvanja
        """
        return self.DECLARATION_POINTS.get(declaration_type, 0)
    
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