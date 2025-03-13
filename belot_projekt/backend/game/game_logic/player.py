"""
Modul koji definira klasu igrača za Belot igru.

Ovaj modul pruža implementaciju klase Player koja predstavlja jednog igrača
u igri Belot, s metodama za upravljanje kartama, potezima i stanjem igrača.
"""

from game.game_logic.card import Card


class Player:
    """
    Klasa koja predstavlja jednog igrača u igri Belot.
    
    Igrač ima svoje osobne podatke, karte u ruci, tim kojem pripada
    i metode za igranje poteza i upravljanje kartama.
    """
    
    def __init__(self, id, username, team=None):
        """
        Inicijalizira novog igrača.
        
        Args:
            id: Jedinstveni identifikator igrača
            username: Korisničko ime igrača
            team: Tim kojem igrač pripada ('a' ili 'b', None ako nije dodijeljen)
        """
        self.id = id
        self.username = username
        self.team = team
        self.hand = []  # Karte u ruci igrača
        self.score = 0  # Osobna statistika bodova
        self.games_played = 0  # Broj odigranih igara
        self.games_won = 0  # Broj pobjeda
        self.is_active = True  # Je li igrač aktivan u igri
        self.is_ready = False  # Je li igrač spreman za početak igre
        self.is_dealer = False  # Je li igrač trenutni djelitelj
    
    def add_card(self, card):
        """
        Dodaje kartu u ruku igrača.
        
        Args:
            card: Karta koja se dodaje (objekt Card ili string)
            
        Returns:
            bool: True ako je karta uspješno dodana, False inače
        """
        # Pretvori string u objekt Card ako je potrebno
        if isinstance(card, str):
            card = Card.from_code(card)
        
        # Provjeri da igrač nema već tu kartu
        if any(c.code == card.code for c in self.hand):
            return False
        
        self.hand.append(card)
        return True
    
    def remove_card(self, card):
        """
        Uklanja kartu iz ruke igrača.
        
        Args:
            card: Karta koja se uklanja (objekt Card ili string)
            
        Returns:
            Card: Uklonjena karta ili None ako karta nije pronađena
        """
        # Pretvori string u objekt Card ako je potrebno
        if isinstance(card, str):
            card_code = card
            for i, c in enumerate(self.hand):
                if c.code == card_code:
                    return self.hand.pop(i)
            return None
        
        # Ako je objekt Card
        if card in self.hand:
            self.hand.remove(card)
            return card
        
        return None
    
    def has_card(self, card):
        """
        Provjerava ima li igrač određenu kartu.
        
        Args:
            card: Karta koja se provjerava (objekt Card ili string)
            
        Returns:
            bool: True ako igrač ima kartu, False inače
        """
        # Pretvori string u kod karte ako je potrebno
        if isinstance(card, str):
            card_code = card
            return any(c.code == card_code for c in self.hand)
        
        # Ako je objekt Card
        return card in self.hand
    
    def get_cards_of_suit(self, suit):
        """
        Vraća sve karte određene boje iz ruke igrača.
        
        Args:
            suit: Boja koja se traži ('S', 'H', 'D', 'C')
            
        Returns:
            list: Lista karata tražene boje
        """
        return [card for card in self.hand if card.suit == suit]
    
    def has_suit(self, suit):
        """
        Provjerava ima li igrač karte određene boje.
        
        Args:
            suit: Boja koja se provjerava ('S', 'H', 'D', 'C')
            
        Returns:
            bool: True ako igrač ima barem jednu kartu tražene boje, False inače
        """
        return any(card.suit == suit for card in self.hand)
    
    def can_play_card(self, card, trick, trump_suit):
        """
        Provjerava može li igrač odigrati određenu kartu prema pravilima igre.
        
        Args:
            card: Karta koju igrač želi odigrati
            trick: Trenutni štih (lista već odigranih karata)
            trump_suit: Adutska boja
            
        Returns:
            bool: True ako se karta može odigrati, False inače
        """
        # Pretvori string u objekt Card ako je potrebno
        if isinstance(card, str):
            card_code = card
            card = next((c for c in self.hand if c.code == card_code), None)
            if not card:
                return False
        
        # Ako igrač nema kartu u ruci, ne može ju odigrati
        if card not in self.hand:
            return False
        
        # Ako je prvi potez u štihu, može se odigrati bilo koja karta
        if not trick:
            return True
        
        # Prva karta u štihu određuje traženu boju
        lead_card = trick[0]
        lead_suit = lead_card.suit
        
        # Ako igrač ima traženu boju, mora ju igrati
        if self.has_suit(lead_suit):
            return card.suit == lead_suit
        
        # Ako igrač nema traženu boju i adut još nije igran, mora igrati aduta ako ga ima
        adut_played = any(c.suit == trump_suit for c in trick)
        if not adut_played and self.has_suit(trump_suit):
            return card.suit == trump_suit
        
        # Ako igrač nema ni traženu boju ni aduta, može igrati bilo koju kartu
        return True
    
    def play_card(self, card, trick, trump_suit):
        """
        Igra kartu iz ruke igrača.
        
        Args:
            card: Karta koju igrač želi odigrati
            trick: Trenutni štih (lista već odigranih karata)
            trump_suit: Adutska boja
            
        Returns:
            Card: Odigrana karta ili None ako potez nije valjan
            
        Raises:
            ValueError: Ako potez nije valjan prema pravilima igre
        """
        # Pretvori string u objekt Card ako je potrebno
        if isinstance(card, str):
            card_code = card
            card = next((c for c in self.hand if c.code == card_code), None)
            if not card:
                raise ValueError(f"Karta {card_code} nije pronađena u ruci igrača")
        
        # Provjeri može li se karta odigrati
        if not self.can_play_card(card, trick, trump_suit):
            raise ValueError("Potez nije valjan prema pravilima igre")
        
        # Ukloni kartu iz ruke i vrati je
        return self.remove_card(card)
    
    def clear_hand(self):
        """
        Uklanja sve karte iz ruke igrača.
        
        Returns:
            list: Lista uklonjenih karata
        """
        cards = self.hand.copy()
        self.hand = []
        return cards
    
    def set_team(self, team):
        """
        Postavlja tim kojem igrač pripada.
        
        Args:
            team: Oznaka tima ('a' ili 'b')
            
        Returns:
            bool: True ako je tim uspješno postavljen, False inače
        """
        if team not in ['a', 'b']:
            return False
        
        self.team = team
        return True
    
    def sort_hand(self):
        """
        Sortira karte u ruci igrača.
        
        Sortira karte po boji (pik, herc, karo, tref) i po vrijednosti
        unutar boje (7, 8, 9, 10, J, Q, K, A).
        
        Returns:
            list: Sortirana ruka
        """
        # Definiranje redoslijeda boja
        suit_order = {'S': 0, 'H': 1, 'D': 2, 'C': 3}
        
        # Definiranje redoslijeda vrijednosti
        value_order = {'7': 0, '8': 1, '9': 2, '10': 3, 'J': 4, 'Q': 5, 'K': 6, 'A': 7}
        
        # Sortiranje karte prvo po boji, zatim po vrijednosti
        self.hand.sort(key=lambda card: (suit_order[card.suit], value_order[card.value]))
        
        return self.hand
    
    def update_stats(self, game_won):
        """
        Ažurira statistiku igrača nakon igre.
        
        Args:
            game_won: Je li igra dobivena
            
        Returns:
            tuple: (games_played, games_won) - nove vrijednosti
        """
        self.games_played += 1
        if game_won:
            self.games_won += 1
        
        return self.games_played, self.games_won
    
    def __str__(self):
        """
        Vraća string reprezentaciju igrača.
        
        Returns:
            str: String s korisničkim imenom igrača
        """
        return self.username
    
    def __repr__(self):
        """
        Vraća reprezentaciju igrača za debagiranje.
        
        Returns:
            str: String s ID-em i korisničkim imenom igrača
        """
        return f"Player(id={self.id}, username='{self.username}', team={self.team})"