"""
Modul koji definira validator zvanja u Belot igri.

Ovaj modul pruža implementaciju klase CallValidator koja je odgovorna za
provjeru valjanosti zvanja (aduta, bele, sekvenci i drugih kombinacija)
prema pravilima Belot igre. Validator osigurava da igrači prijavljuju
samo zvanja koja su valjana i koja posjeduju u svojim rukama.
"""

from game.game_logic.card import Card


class CallValidator:
    """
    Klasa koja validira zvanja u Belot igri.
    
    Provjerava jesu li zvanja aduta, bele i drugih kombinacija valjana
    prema pravilima Belota, uključujući posjedovanje odgovarajućih karata
    i poštivanje strukture zvanja.
    """
    
    # Valjane boje za aduta
    VALID_TRUMP_SUITS = ['spades', 'hearts', 'diamonds', 'clubs']
    
    # Sekvence karata za provjeru nizova
    VALID_SEQUENCES = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    
    # Prioriteti zvanja (od najvišeg prema najnižem)
    DECLARATION_PRIORITIES = {
        'belot': 1001,        # Osam karata u istoj boji u nizu
        'four_jacks': 200,    # Četiri dečka
        'four_nines': 150,    # Četiri devetke
        'four_aces': 100,     # Četiri asa
        'four_kings': 100,    # Četiri kralja
        'four_queens': 100,   # Četiri dame
        'sequence_5_plus': 100,  # Pet ili više karata u istoj boji u nizu
        'sequence_4': 50,     # Četiri karte u istoj boji u nizu
        'sequence_3': 20,     # Tri karte u istoj boji u nizu
        'bela': 20            # Kralj i dama iste boje u adutu
    }
    
    def __init__(self):
        """Inicijalizira validator zvanja."""
        pass
    
    def validate(self, declaration_type, cards, trump_suit=None):
        """
        Glavna metoda za validaciju zvanja (alias za validate_declaration).
        
        Args:
            declaration_type: Tip zvanja (npr. 'sequence_3', 'four_jacks')
            cards: Lista karata koje čine zvanje
            trump_suit: Adutska boja (opcionalno, potrebno za belu)
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije)
        """
        return self.validate_declaration(declaration_type, cards, trump_suit)
    
    def can_declare(self, player_hand, declaration_type, trump_suit=None):
        """
        Provjerava može li igrač proglasiti određeno zvanje s kartama koje ima.
        
        Args:
            player_hand: Lista karata u ruci igrača
            declaration_type: Tip zvanja (npr. 'sequence_3', 'four_jacks')
            trump_suit: Adutska boja (opcionalno, potrebno za belu)
            
        Returns:
            tuple: (bool, list) - (može li proglasiti, karte koje čine zvanje)
        """
        # Za belu (kralj i dama u adutu)
        if declaration_type == 'bela':
            if not trump_suit:
                return False, []
                
            trump_suit_code = self._normalize_suit(trump_suit)
            trump_cards = [card for card in player_hand if card.suit == trump_suit_code]
            
            king = next((card for card in trump_cards if card.value == 'K'), None)
            queen = next((card for card in trump_cards if card.value == 'Q'), None)
            
            if king and queen:
                return True, [king, queen]
            return False, []
        
        # Za četiri iste karte
        if declaration_type.startswith('four_'):
            expected_value = None
            if declaration_type == 'four_jacks':
                expected_value = 'J'
            elif declaration_type == 'four_nines':
                expected_value = '9'
            elif declaration_type == 'four_aces':
                expected_value = 'A'
            elif declaration_type == 'four_tens':
                expected_value = '10'
            elif declaration_type == 'four_kings':
                expected_value = 'K'
            elif declaration_type == 'four_queens':
                expected_value = 'Q'
            else:
                return False, []
                
            matching_cards = [card for card in player_hand if card.value == expected_value]
            if len(matching_cards) == 4:
                return True, matching_cards
            return False, []
        
        # Za sekvence
        if declaration_type.startswith('sequence_'):
            min_length = 0
            if declaration_type == 'sequence_3':
                min_length = 3
            elif declaration_type == 'sequence_4':
                min_length = 4
            elif declaration_type == 'sequence_5_plus':
                min_length = 5
            else:
                return False, []
                
            # Grupiraj karte po bojama
            suit_groups = {}
            for card in player_hand:
                if card.suit not in suit_groups:
                    suit_groups[card.suit] = []
                suit_groups[card.suit].append(card)
            
            # Provjeri svaku grupu za sekvence
            for suit, cards in suit_groups.items():
                # Sortiranje karata po vrijednosti
                cards.sort(key=lambda c: self.VALID_SEQUENCES.index(c.value))
                
                # Traži najdulji niz
                sequences = self._find_sequences(cards)
                for sequence in sequences:
                    if len(sequence) >= min_length:
                        return True, sequence
            
            return False, []
        
        # Za belot (8 karata iste boje)
        if declaration_type == 'belot':
            suit_groups = {}
            for card in player_hand:
                if card.suit not in suit_groups:
                    suit_groups[card.suit] = []
                suit_groups[card.suit].append(card)
            
            for suit, cards in suit_groups.items():
                if len(cards) == 8:
                    return True, cards
            
            return False, []
            
        return False, []
    
    def check_priority(self, declarations_list):
        """
        Određuje koje zvanje ima najveći prioritet.
        
        Args:
            declarations_list: Lista zvanja (rječnici s tipom i vrijednošću)
            
        Returns:
            int: Indeks zvanja s najvišim prioritetom ili -1 ako je lista prazna
        """
        if not declarations_list:
            return -1
            
        highest_priority = -1
        highest_index = -1
        
        for i, declaration in enumerate(declarations_list):
            priority = self.DECLARATION_PRIORITIES.get(declaration['type'], 0)
            if priority > highest_priority:
                highest_priority = priority
                highest_index = i
        
        return highest_index
    
    def validate_trump_call(self, suit):
        """
        Provjerava valjanost zvanja aduta.
        
        Args:
            suit: Boja za aduta (spades, hearts, diamonds, clubs)
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije)
        """
        if not suit:
            return False, "Neispravan unos: adut ne može biti prazno."
        
        if suit not in self.VALID_TRUMP_SUITS:
            return False, f"Nepoznat izbor aduta: {suit}. Valjani izbori su: pik, herc, karo, tref."
        
        return True, ""
    
    def validate_bela(self, cards, trump_suit):
        """
        Provjerava valjanost zvanja bele (kralj i dama u adutu).
        
        Args:
            cards: Lista karata za belu
            trump_suit: Adutska boja
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije)
        """
        # Provjera je li adut definiran
        if not trump_suit:
            return False, "Adut nije definiran, nije moguće zvati belu."
        
        # Pretvaranje stringa u kod karte ako je potrebno
        card_codes = []
        for card in cards:
            if isinstance(card, str):
                card_codes.append(card)
            else:
                card_codes.append(card.code)
        
        # Normalizacija adutske boje
        trump_suit_code = self._normalize_suit(trump_suit)
        
        # Bela zahtijeva kralja i damu iste boje u adutu
        if len(card_codes) != 2:
            return False, "Bela mora sadržavati točno dvije karte: kralja i damu aduta."
        
        # Sortiranje po vrijednosti
        values = [code[:-1] for code in card_codes]
        suits = [code[-1] for code in card_codes]
        
        # Provjera vrijednosti
        if sorted(values) != ['K', 'Q']:
            return False, "Bela mora sadržavati kralja i damu, ne druge karte."
        
        # Provjera boje
        if not all(suit == trump_suit_code for suit in suits):
            return False, f"Bela mora biti u adutskoj boji ({self._suit_name(trump_suit_code)})."
        
        return True, ""
    
    def validate_declaration(self, declaration_type, cards, trump_suit=None):
        """
        Provjerava valjanost zvanja (sekvence, četiri iste karte, belot).
        
        Args:
            declaration_type: Tip zvanja (sequence_3, sequence_4, sequence_5_plus, 
                             four_jacks, four_nines, four_aces, itd.)
            cards: Lista karata koje čine zvanje
            trump_suit: Adutska boja (opcionalno, potrebno za belu)
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije)
        """
        # Provjera zvanja bele
        if declaration_type == 'bela':
            return self.validate_bela(cards, trump_suit)
        
        # Pretvaranje stringa u kod karte ako je potrebno
        card_codes = []
        for card in cards:
            if isinstance(card, str):
                card_codes.append(card)
            else:
                card_codes.append(card.code)
        
        # Provjere za sekvence (terca, kvarta, kvinta, itd.)
        if declaration_type.startswith('sequence_'):
            return self.validate_sequence(card_codes, declaration_type)
        
        # Provjere za četiri iste karte (četiri dečka, četiri devetke, itd.)
        elif declaration_type.startswith('four_'):
            return self.validate_four_of_kind(card_codes, declaration_type)
        
        # Provjera za belot (osam karata u nizu iste boje)
        elif declaration_type == 'belot':
            return self.validate_belot(card_codes)
        
        else:
            return False, f"Nepoznat tip zvanja: {declaration_type}."
    
    def validate_sequence(self, card_codes, declaration_type):
        """
        Provjerava valjanost zvanja sekvence (terca, kvarta, kvinta, itd.).
        
        Args:
            card_codes: Lista kodova karata koje čine zvanje
            declaration_type: Tip sekvence (sequence_3, sequence_4, sequence_5_plus)
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije)
        """
        # Određivanje minimalne duljine sekvence
        min_length = 0
        if declaration_type == 'sequence_3':
            min_length = 3
        elif declaration_type == 'sequence_4':
            min_length = 4
        elif declaration_type == 'sequence_5_plus':
            min_length = 5
        else:
            return False, f"Nepoznat tip sekvence: {declaration_type}."
        
        # Provjera duljine sekvence
        if len(card_codes) < min_length:
            return False, f"Sekvenca mora sadržavati barem {min_length} karata u nizu."
        
        # Provjera iste boje
        suits = [code[-1] for code in card_codes]
        if len(set(suits)) != 1:
            return False, "Sve karte u sekvenci moraju biti iste boje."
        
        # Izdvajanje vrijednosti i sortiranje
        values = [code[:-1] for code in card_codes]
        
        # Provjera sekvence (karte moraju biti u nizu)
        value_indices = []
        for value in values:
            if value not in self.VALID_SEQUENCES:
                return False, f"Nevažeća vrijednost karte u sekvenci: {value}."
            value_indices.append(self.VALID_SEQUENCES.index(value))
        
        value_indices.sort()
        
        # Provjera kontinuiteta sekvence
        for i in range(1, len(value_indices)):
            if value_indices[i] != value_indices[i-1] + 1:
                return False, "Karte u sekvenci moraju biti u nizu (npr. 7-8-9 ili J-Q-K)."
        
        return True, ""
    
    def validate_four_of_kind(self, card_codes, declaration_type):
        """
        Provjerava valjanost zvanja četiri iste karte.
        
        Args:
            card_codes: Lista kodova karata koje čine zvanje
            declaration_type: Tip zvanja (four_jacks, four_nines, four_aces, itd.)
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije)
        """
        # Određivanje očekivane vrijednosti
        expected_value = None
        if declaration_type == 'four_jacks':
            expected_value = 'J'
        elif declaration_type == 'four_nines':
            expected_value = '9'
        elif declaration_type == 'four_aces':
            expected_value = 'A'
        elif declaration_type == 'four_tens':
            expected_value = '10'
        elif declaration_type == 'four_kings':
            expected_value = 'K'
        elif declaration_type == 'four_queens':
            expected_value = 'Q'
        else:
            return False, f"Nepoznat tip zvanja četiri iste karte: {declaration_type}."
        
        # Provjera broja karata
        if len(card_codes) != 4:
            return False, f"Zvanje {declaration_type} mora sadržavati točno 4 karte."
        
        # Izdvajanje vrijednosti i boja
        values = [code[:-1] for code in card_codes]
        suits = [code[-1] for code in card_codes]
        
        # Provjera vrijednosti
        if not all(value == expected_value for value in values):
            return False, f"Sve karte u zvanju {declaration_type} moraju biti {expected_value}."
        
        # Provjera zastupljenosti svih boja
        if len(set(suits)) != 4:
            return False, "Zvanje mora sadržavati po jednu kartu svake boje (pik, herc, karo, tref)."
        
        return True, ""
    
    def validate_belot(self, card_codes):
        """
        Provjerava valjanost zvanja belot (osam karata u nizu iste boje).
        
        Args:
            card_codes: Lista kodova karata koje čine zvanje
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije)
        """
        # Provjera broja karata
        if len(card_codes) != 8:
            return False, "Belot mora sadržavati svih 8 karata iste boje (7 do A)."
        
        # Provjera iste boje
        suits = [code[-1] for code in card_codes]
        if len(set(suits)) != 1:
            return False, "Sve karte u belotu moraju biti iste boje."
        
        # Izdvajanje vrijednosti
        values = [code[:-1] for code in card_codes]
        
        # Provjera zastupljenosti svih vrijednosti
        expected_values = set(self.VALID_SEQUENCES)
        actual_values = set(values)
        
        if actual_values != expected_values:
            missing = expected_values - actual_values
            return False, f"Belot mora sadržavati sve karte od 7 do A. Nedostaju: {', '.join(missing)}."
        
        return True, ""
    
    def _find_sequences(self, sorted_cards):
        """
        Pronalazi sve sekvence u listi sortiranih karata.
        
        Args:
            sorted_cards: Lista karata sortiranih po vrijednosti
            
        Returns:
            list: Lista sekvenci (svaka sekvenca je lista karata)
        """
        if not sorted_cards:
            return []
            
        sequences = []
        current_sequence = [sorted_cards[0]]
        
        for i in range(1, len(sorted_cards)):
            # Ako je trenutna karta za 1 veća od prethodne, dodaj u sekvencu
            prev_idx = self.VALID_SEQUENCES.index(sorted_cards[i-1].value)
            curr_idx = self.VALID_SEQUENCES.index(sorted_cards[i].value)
            
            if curr_idx == prev_idx + 1:
                current_sequence.append(sorted_cards[i])
            else:
                # Završi sekvencu ako je dovoljno duga
                if len(current_sequence) >= 3:
                    sequences.append(current_sequence.copy())
                # Započni novu sekvencu
                current_sequence = [sorted_cards[i]]
        
        # Dodaj posljednju sekvencu ako je dovoljno duga
        if len(current_sequence) >= 3:
            sequences.append(current_sequence)
            
        return sequences
    
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
        Vraća čitljivo ime boje na hrvatskom.
        
        Args:
            suit_code: Kod boje ('S', 'H', 'D', 'C')
            
        Returns:
            str: Čitljivo ime boje
        """
        suit_names = {
            'S': 'pik',
            'H': 'herc',
            'D': 'karo',
            'C': 'tref'
        }
        return suit_names.get(suit_code, suit_code)