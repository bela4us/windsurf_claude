"""
Modul koji definira validator zvanja u Belot igri.

Ovaj modul pruža implementaciju klase CallValidator koja je odgovorna za
provjeru valjanosti zvanja (aduta, bele, sekvenci i drugih kombinacija)
prema pravilima Belot igre. Validator osigurava da igrači prijavljuju
samo zvanja koja su valjana i koja posjeduju u svojim rukama.
"""

import logging
from functools import lru_cache
from game.game_logic.card import Card
from game.utils.decorators import track_execution_time

# Postavljanje loggera za praćenje aktivnosti
logger = logging.getLogger(__name__)

class CallValidator:
    """
    Klasa koja validira zvanja u Belot igri.
    
    Provjerava jesu li zvanja aduta, bele i drugih kombinacija valjana
    prema pravilima Belota, uključujući posjedovanje odgovarajućih karata
    i poštivanje strukture zvanja.
    
    Attributes:
        VALID_TRUMP_SUITS (list): Valjane boje za aduta.
        VALID_SEQUENCES (list): Sekvence karata za provjeru nizova.
        DECLARATION_PRIORITIES (dict): Prioriteti zvanja (od najvišeg prema najnižem).
        _cache_enabled (bool): Označava je li keširanje omogućeno.
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
        """
        Inicijalizira validator zvanja.
        
        Postavlja početno stanje validatora i inicijalizira internu keš memoriju.
        """
        self._cache_enabled = True
        logger.info("CallValidator inicijaliziran")
    
    def _invalidate_cache(self):
        """
        Poništava sve keširane vrijednosti.
        
        Ova metoda se poziva kad se promijeni stanje koje bi moglo utjecati na rezultate keširanih metoda.
        """
        if hasattr(self._normalize_suit, 'cache_clear'):
            self._normalize_suit.cache_clear()
        if hasattr(self._suit_name, 'cache_clear'):
            self._suit_name.cache_clear()
        logger.debug("Keš memorija CallValidator-a je poništena")
    
    @track_execution_time
    def validate(self, declaration_type, cards, trump_suit=None):
        """
        Glavna metoda za validaciju zvanja (alias za validate_declaration).
        
        Args:
            declaration_type (str): Tip zvanja (npr. 'sequence_3', 'four_jacks').
            cards (list): Lista karata koje čine zvanje.
            trump_suit (str, optional): Adutska boja. Zadano je None.
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije).
        
        Primjer:
            >>> validator.validate('bela', [Card('KH'), Card('QH')], 'hearts')
            (True, '')
        """
        try:
            logger.info(f"Validacija zvanja: {declaration_type} s {len(cards)} karata, adut: {trump_suit}")
            return self.validate_declaration(declaration_type, cards, trump_suit)
        except Exception as e:
            logger.error(f"Greška prilikom validacije zvanja: {str(e)}")
            return False, f"Interna greška prilikom validacije zvanja: {str(e)}"
    
    @track_execution_time
    def can_declare(self, player_hand, declaration_type, trump_suit=None):
        """
        Provjerava može li igrač proglasiti određeno zvanje s kartama koje ima.
        
        Args:
            player_hand (list): Lista karata u ruci igrača.
            declaration_type (str): Tip zvanja (npr. 'sequence_3', 'four_jacks').
            trump_suit (str, optional): Adutska boja. Zadano je None.
            
        Returns:
            tuple: (bool, list) - (može li proglasiti, karte koje čine zvanje).
        
        Raises:
            ValueError: Ako je igraču ruka prazna ili parametri nisu valjani.
        """
        try:
            if not player_hand:
                logger.warning("Pokušaj provjere zvanja s praznom rukom")
                return False, []
                
            if not declaration_type:
                logger.warning("Pokušaj provjere zvanja bez navedenog tipa zvanja")
                return False, []
                
            logger.info(f"Provjera mogućnosti zvanja: {declaration_type} za igrača s {len(player_hand)} karata")
            
            # Za belu (kralj i dama u adutu)
            if declaration_type == 'bela':
                if not trump_suit:
                    logger.debug("Provjera bele bez aduta - nije moguće")
                    return False, []
                    
                trump_suit_code = self._normalize_suit(trump_suit)
                trump_cards = [card for card in player_hand if card.suit == trump_suit_code]
                
                king = next((card for card in trump_cards if card.value == 'K'), None)
                queen = next((card for card in trump_cards if card.value == 'Q'), None)
                
                if king and queen:
                    logger.info(f"Pronađena bela u {self._suit_name(trump_suit_code)}")
                    return True, [king, queen]
                logger.debug(f"Bela nije pronađena u {self._suit_name(trump_suit_code)}")
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
                    logger.warning(f"Nepoznat tip zvanja: {declaration_type}")
                    return False, []
                    
                matching_cards = [card for card in player_hand if card.value == expected_value]
                if len(matching_cards) == 4:
                    logger.info(f"Pronađeno zvanje: {declaration_type}")
                    return True, matching_cards
                logger.debug(f"Zvanje {declaration_type} nije pronađeno, pronađeno {len(matching_cards)} od 4 karte")
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
                    logger.warning(f"Nepoznat tip sekvence: {declaration_type}")
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
                            logger.info(f"Pronađena sekvenca duljine {len(sequence)} u {self._suit_name(suit)}")
                            return True, sequence
                
                logger.debug(f"Sekvenca tipa {declaration_type} nije pronađena")
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
                        logger.info(f"Pronađen belot u {self._suit_name(suit)}")
                        return True, cards
                
                logger.debug("Belot nije pronađen")
                return False, []
                
            logger.warning(f"Nepoznat tip zvanja: {declaration_type}")
            return False, []
            
        except Exception as e:
            logger.error(f"Greška prilikom provjere mogućnosti zvanja: {str(e)}")
            return False, []
    
    @track_execution_time
    def check_priority(self, declarations_list):
        """
        Određuje koje zvanje ima najveći prioritet.
        
        Args:
            declarations_list (list): Lista zvanja (rječnici s tipom i vrijednošću).
            
        Returns:
            int: Indeks zvanja s najvišim prioritetom ili -1 ako je lista prazna.
        
        Raises:
            ValueError: Ako ulazna lista nije u ispravnom formatu.
        """
        try:
            if not declarations_list:
                logger.debug("Provjera prioriteta za praznu listu zvanja")
                return -1
                
            highest_priority = -1
            highest_index = -1
            
            for i, declaration in enumerate(declarations_list):
                if not isinstance(declaration, dict) or 'type' not in declaration:
                    logger.warning(f"Nevažeći format zvanja na indeksu {i}: {declaration}")
                    continue
                    
                priority = self.DECLARATION_PRIORITIES.get(declaration['type'], 0)
                logger.debug(f"Zvanje: {declaration['type']}, prioritet: {priority}")
                if priority > highest_priority:
                    highest_priority = priority
                    highest_index = i
            
            logger.info(f"Pronađeno zvanje s najvišim prioritetom na indeksu {highest_index}, prioritet: {highest_priority}")
            return highest_index
            
        except Exception as e:
            logger.error(f"Greška prilikom određivanja prioriteta zvanja: {str(e)}")
            return -1
    
    @track_execution_time
    def validate_trump_call(self, suit):
        """
        Provjerava valjanost zvanja aduta.
        
        Args:
            suit (str): Boja za aduta (spades, hearts, diamonds, clubs).
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije).
        """
        try:
            logger.info(f"Validacija zvanja aduta: {suit}")
            
            if not suit:
                logger.warning("Pokušaj zvanja aduta bez navedene boje")
                return False, "Neispravan unos: adut ne može biti prazno."
            
            if suit not in self.VALID_TRUMP_SUITS:
                logger.warning(f"Nevažeća boja aduta: {suit}")
                return False, f"Nepoznat izbor aduta: {suit}. Valjani izbori su: pik, herc, karo, tref."
            
            logger.debug(f"Uspješna validacija aduta: {suit}")
            return True, ""
            
        except Exception as e:
            logger.error(f"Greška prilikom validacije aduta: {str(e)}")
            return False, f"Interna greška prilikom validacije aduta: {str(e)}"
    
    @track_execution_time
    def validate_bela(self, cards, trump_suit):
        """
        Provjerava valjanost zvanja bele (kralj i dama u adutu).
        
        Args:
            cards (list): Lista karata za belu.
            trump_suit (str): Adutska boja.
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije).
        """
        try:
            logger.info(f"Validacija zvanja bele s {len(cards)} karata, adut: {trump_suit}")
            
            # Provjera je li adut definiran
            if not trump_suit:
                logger.warning("Pokušaj zvanja bele bez aduta")
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
                logger.warning(f"Bela mora imati točno 2 karte, pronađeno {len(card_codes)}")
                return False, "Bela mora sadržavati točno dvije karte: kralja i damu aduta."
            
            # Sortiranje po vrijednosti
            values = [code[:-1] for code in card_codes]
            suits = [code[-1] for code in card_codes]
            
            # Provjera vrijednosti
            if sorted(values) != ['K', 'Q']:
                logger.warning(f"Bela mora sadržavati kralja i damu, pronađeno: {values}")
                return False, "Bela mora sadržavati kralja i damu, ne druge karte."
            
            # Provjera boje
            if not all(suit == trump_suit_code for suit in suits):
                logger.warning(f"Karte u beli nisu sve u adutskoj boji: {suits}, adut: {trump_suit_code}")
                return False, f"Bela mora biti u adutskoj boji ({self._suit_name(trump_suit_code)})."
            
            logger.debug("Uspješna validacija bele")
            return True, ""
            
        except Exception as e:
            logger.error(f"Greška prilikom validacije bele: {str(e)}")
            return False, f"Interna greška prilikom validacije bele: {str(e)}"
    
    @track_execution_time
    def validate_declaration(self, declaration_type, cards, trump_suit=None):
        """
        Provjerava valjanost zvanja (sekvence, četiri iste karte, belot).
        
        Args:
            declaration_type (str): Tip zvanja (sequence_3, sequence_4, sequence_5_plus, 
                                four_jacks, four_nines, four_aces, itd.).
            cards (list): Lista karata koje čine zvanje.
            trump_suit (str, optional): Adutska boja. Zadano je None.
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije).
        """
        try:
            logger.info(f"Validacija zvanja: {declaration_type} s {len(cards)} karata")
            
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
                logger.warning(f"Nepoznat tip zvanja: {declaration_type}")
                return False, f"Nepoznat tip zvanja: {declaration_type}."
                
        except Exception as e:
            logger.error(f"Greška prilikom validacije zvanja: {str(e)}")
            return False, f"Interna greška prilikom validacije zvanja: {str(e)}"
    
    @track_execution_time
    def validate_sequence(self, card_codes, declaration_type):
        """
        Provjerava valjanost zvanja sekvence (terca, kvarta, kvinta, itd.).
        
        Args:
            card_codes (list): Lista kodova karata koje čine zvanje.
            declaration_type (str): Tip sekvence (sequence_3, sequence_4, sequence_5_plus).
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije).
        """
        try:
            logger.info(f"Validacija sekvence: {declaration_type} s {len(card_codes)} karata")
            
            # Određivanje minimalne duljine sekvence
            min_length = 0
            if declaration_type == 'sequence_3':
                min_length = 3
            elif declaration_type == 'sequence_4':
                min_length = 4
            elif declaration_type == 'sequence_5_plus':
                min_length = 5
            else:
                logger.warning(f"Nepoznat tip sekvence: {declaration_type}")
                return False, f"Nepoznat tip sekvence: {declaration_type}."
            
            # Provjera duljine sekvence
            if len(card_codes) < min_length:
                logger.warning(f"Nedovoljna duljina sekvence: {len(card_codes)}, potrebno: {min_length}")
                return False, f"Sekvenca mora sadržavati barem {min_length} karata u nizu."
            
            # Provjera iste boje
            suits = [code[-1] for code in card_codes]
            if len(set(suits)) != 1:
                logger.warning(f"Karte u sekvenci nisu iste boje: {suits}")
                return False, "Sve karte u sekvenci moraju biti iste boje."
            
            # Izdvajanje vrijednosti i sortiranje
            values = [code[:-1] for code in card_codes]
            
            # Provjera sekvence (karte moraju biti u nizu)
            value_indices = []
            for value in values:
                if value not in self.VALID_SEQUENCES:
                    logger.warning(f"Nevažeća vrijednost karte u sekvenci: {value}")
                    return False, f"Nevažeća vrijednost karte u sekvenci: {value}."
                value_indices.append(self.VALID_SEQUENCES.index(value))
            
            value_indices.sort()
            
            # Provjera kontinuiteta sekvence
            for i in range(1, len(value_indices)):
                if value_indices[i] != value_indices[i-1] + 1:
                    logger.warning(f"Sekvenca nije kontinuirana: {value_indices}")
                    return False, "Karte u sekvenci moraju biti u nizu (npr. 7-8-9 ili J-Q-K)."
            
            logger.debug("Uspješna validacija sekvence")
            return True, ""
            
        except Exception as e:
            logger.error(f"Greška prilikom validacije sekvence: {str(e)}")
            return False, f"Interna greška prilikom validacije sekvence: {str(e)}"
    
    @track_execution_time
    def validate_four_of_kind(self, card_codes, declaration_type):
        """
        Provjerava valjanost zvanja četiri iste karte.
        
        Args:
            card_codes (list): Lista kodova karata koje čine zvanje.
            declaration_type (str): Tip zvanja (four_jacks, four_nines, four_aces, itd.).
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije).
        """
        try:
            logger.info(f"Validacija četiri iste karte: {declaration_type}")
            
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
                logger.warning(f"Nepoznat tip zvanja četiri iste karte: {declaration_type}")
                return False, f"Nepoznat tip zvanja četiri iste karte: {declaration_type}."
            
            # Provjera broja karata
            if len(card_codes) != 4:
                logger.warning(f"Netočan broj karata: {len(card_codes)}, potrebno: 4")
                return False, f"Zvanje {declaration_type} mora sadržavati točno 4 karte."
            
            # Izdvajanje vrijednosti i boja
            values = [code[:-1] for code in card_codes]
            suits = [code[-1] for code in card_codes]
            
            # Provjera vrijednosti
            if not all(value == expected_value for value in values):
                logger.warning(f"Nisu sve karte istog ranga: {values}, očekivano: {expected_value}")
                return False, f"Sve karte u zvanju {declaration_type} moraju biti {expected_value}."
            
            # Provjera zastupljenosti svih boja
            if len(set(suits)) != 4:
                logger.warning(f"Nisu zastupljene sve boje: {set(suits)}")
                return False, "Zvanje mora sadržavati po jednu kartu svake boje (pik, herc, karo, tref)."
            
            logger.debug("Uspješna validacija četiri iste karte")
            return True, ""
            
        except Exception as e:
            logger.error(f"Greška prilikom validacije četiri iste karte: {str(e)}")
            return False, f"Interna greška prilikom validacije zvanja četiri iste karte: {str(e)}"
    
    @track_execution_time
    def validate_belot(self, card_codes):
        """
        Provjerava valjanost zvanja belot (osam karata u nizu iste boje).
        
        Args:
            card_codes (list): Lista kodova karata koje čine zvanje.
            
        Returns:
            tuple: (bool, str) - (je li zvanje valjano, razlog ako nije).
        """
        try:
            logger.info(f"Validacija belota s {len(card_codes)} karata")
            
            # Provjera broja karata
            if len(card_codes) != 8:
                logger.warning(f"Netočan broj karata: {len(card_codes)}, potrebno: 8")
                return False, "Belot mora sadržavati svih 8 karata iste boje (7 do A)."
            
            # Provjera iste boje
            suits = [code[-1] for code in card_codes]
            if len(set(suits)) != 1:
                logger.warning(f"Karte u belotu nisu iste boje: {suits}")
                return False, "Sve karte u belotu moraju biti iste boje."
            
            # Izdvajanje vrijednosti
            values = [code[:-1] for code in card_codes]
            
            # Provjera zastupljenosti svih vrijednosti
            expected_values = set(self.VALID_SEQUENCES)
            actual_values = set(values)
            
            if actual_values != expected_values:
                missing = expected_values - actual_values
                logger.warning(f"Nedostaju karte u belotu: {missing}")
                return False, f"Belot mora sadržavati sve karte od 7 do A. Nedostaju: {', '.join(missing)}."
            
            logger.debug("Uspješna validacija belota")
            return True, ""
            
        except Exception as e:
            logger.error(f"Greška prilikom validacije belota: {str(e)}")
            return False, f"Interna greška prilikom validacije belota: {str(e)}"
    
    @track_execution_time
    def _find_sequences(self, sorted_cards):
        """
        Pronalazi sve sekvence u listi sortiranih karata.
        
        Args:
            sorted_cards (list): Lista karata sortiranih po vrijednosti.
            
        Returns:
            list: Lista sekvenci (svaka sekvenca je lista karata).
        """
        try:
            if not sorted_cards:
                logger.debug("Prazna lista karata za traženje sekvenci")
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
                        logger.debug(f"Pronađena sekvenca duljine {len(current_sequence)}")
                    # Započni novu sekvencu
                    current_sequence = [sorted_cards[i]]
            
            # Dodaj posljednju sekvencu ako je dovoljno duga
            if len(current_sequence) >= 3:
                sequences.append(current_sequence)
                logger.debug(f"Pronađena posljednja sekvenca duljine {len(current_sequence)}")
                
            logger.info(f"Ukupno pronađeno {len(sequences)} sekvenci")
            return sequences
            
        except Exception as e:
            logger.error(f"Greška prilikom traženja sekvenci: {str(e)}")
            return []
    
    @lru_cache(maxsize=32)
    def _normalize_suit(self, suit):
        """
        Pretvara puno ime boje u kod boje.
        
        Args:
            suit (str): Boja (puno ime ili kod).
            
        Returns:
            str: Kod boje ('S', 'H', 'D', 'C').
        """
        try:
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
            normalized = suit_map.get(suit.lower(), suit)
            logger.debug(f"Normalizirana boja: {suit} -> {normalized}")
            return normalized
            
        except Exception as e:
            logger.error(f"Greška prilikom normalizacije boje: {str(e)}")
            # Vraćamo izvornu vrijednost kao fallback
            return suit
    
    @lru_cache(maxsize=32)
    def _suit_name(self, suit_code):
        """
        Vraća čitljivo ime boje na hrvatskom.
        
        Args:
            suit_code (str): Kod boje ('S', 'H', 'D', 'C').
            
        Returns:
            str: Čitljivo ime boje.
        """
        try:
            suit_names = {
                'S': 'pik',
                'H': 'herc',
                'D': 'karo',
                'C': 'tref'
            }
            name = suit_names.get(suit_code, suit_code)
            logger.debug(f"Dohvaćeno ime boje: {suit_code} -> {name}")
            return name
            
        except Exception as e:
            logger.error(f"Greška prilikom dohvaćanja imena boje: {str(e)}")
            # Vraćamo izvornu vrijednost kao fallback
            return suit_code