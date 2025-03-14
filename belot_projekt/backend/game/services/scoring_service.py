"""
Servis za bodovanje Belot igre.

Ovaj modul implementira ScoringService klasu koja sadrži svu logiku
vezanu uz bodovanje u Belot igri, uključujući bodovanje karata, zvanja,
izračun rezultata rundi i određivanje pobjednika.
"""

import logging
import functools
from collections import defaultdict
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache

from game.models import Game, Round, Move, Declaration
from game.game_logic.card import Card
from utils.decorators import track_execution_time

User = get_user_model()
logger = logging.getLogger('game.services')

# Keš za rezultate bodovanja
def scoring_cache(timeout=300):
    """
    Dekorator za keširanje rezultata bodovanja.
    
    Kešira rezultat metode na temelju ključa koji se generira iz argumenata.
    
    Args:
        timeout: Vrijeme života keša u sekundama
        
    Returns:
        Dekorirana funkcija
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generiraj ključ za keš
            key_parts = [func.__name__]
            
            # Dodaj argumente u ključ
            for arg in args[1:]:  # Preskačemo self
                key_parts.append(str(arg))
            
            # Dodaj imenovane argumente u ključ
            for k, v in sorted(kwargs.items()):
                key_parts.append(f"{k}:{v}")
            
            cache_key = "scoring:" + ":".join(key_parts)
            
            # Provjeri je li rezultat u kešu
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Izračunaj rezultat
            result = func(*args, **kwargs)
            
            # Spremi rezultat u keš
            cache.set(cache_key, result, timeout)
            
            return result
        
        return wrapper
    
    return decorator

def invalidate_scoring_cache(round_id=None, game_id=None):
    """
    Poništava keš za bodovanje.
    
    Ako je naveden round_id, poništava samo keš za tu rundu.
    Ako je naveden game_id, poništava keš za sve runde u toj igri.
    Ako nije navedeno ništa, poništava sav keš za bodovanje.
    
    Args:
        round_id: ID runde
        game_id: ID igre
    """
    if round_id:
        cache.delete(f"scoring:calculate_tricks_points:{round_id}")
        cache.delete(f"scoring:calculate_declarations_points:{round_id}")
        cache.delete(f"scoring:calculate_round_points:{round_id}")
    elif game_id:
        # Poništi keš za sve runde u igri (prefiks ključeva)
        keys = cache.keys("scoring:*")
        for key in keys:
            if f"game_id:{game_id}" in key:
                cache.delete(key)
    else:
        # Poništi sav keš za bodovanje
        keys = cache.keys("scoring:*")
        for key in keys:
            cache.delete(key)

class ScoringService:
    """
    Servis koji upravlja bodovanjem Belot igre.
    
    Ova klasa sadrži metode za sve aspekte bodovanja igre, uključujući
    izračun vrijednosti karata, bodovanje zvanja, izračun rezultata rundi
    i određivanje pobjednika igre.
    """
    
    # Konstante za bodovanje karata
    NON_TRUMP_CARD_VALUES = {
        'A': 11,
        '10': 10,
        'K': 4,
        'Q': 3,
        'J': 2,
        '9': 0,
        '8': 0,
        '7': 0
    }
    
    TRUMP_CARD_VALUES = {
        'J': 20,
        '9': 14,
        'A': 11,
        '10': 10,
        'K': 4,
        'Q': 3,
        '8': 0,
        '7': 0
    }
    
    # Konstante za bodovanje zvanja
    DECLARATION_VALUES = {
        'belot': 1001,  # Osam karata u istoj boji u nizu
        'four_jacks': 200,  # Četiri dečka
        'four_nines': 150,  # Četiri devetke
        'four_aces': 100,  # Četiri asa
        'four_tens': 100,  # Četiri desetke
        'four_kings': 100,  # Četiri kralja
        'four_queens': 100,  # Četiri dame
        'sequence_5_plus': 100,  # Pet, šest ili sedam karata u nizu iste boje
        'sequence_4': 50,  # Četiri karte u nizu iste boje
        'sequence_3': 20,  # Tri karte u nizu iste boje
        'bela': 20,  # Kralj i dama iste boje u adutu
    }
    
    # Ukupan broj bodova u jednoj rundi (bez zvanja)
    TOTAL_ROUND_POINTS = 162  # 152 bodova za karte + 10 za zadnji štih
    
    # Bodovi za štih-mač (štilju)
    CLEAN_SWEEP_BONUS = 90
    
    # Dodatni bodovi za zadnji štih
    LAST_TRICK_BONUS = 10
    
    @staticmethod
    @track_execution_time
    def calculate_card_value(card_code, trump_suit):
        """
        Izračunava bodovnu vrijednost karte ovisno o tome je li adut.
        
        Args:
            card_code: Kod karte (npr. "7S", "AH", "JD")
            trump_suit: Adutska boja (S, H, D, C) ili None za bez aduta
            
        Returns:
            int: Bodovna vrijednost karte
            
        Raises:
            ValueError: Ako je card_code nevaljan
        """
        try:
            if not card_code or len(card_code) < 2:
                logger.warning(f"Nevažeći kod karte: {card_code}")
                return 0
            
            value = card_code[:-1]  # Npr. "7", "10", "A"
            suit = card_code[-1]  # Npr. "S", "H", "D", "C"
            
            # U varijanti "sve adut" sve boje su adut
            # U varijanti "bez aduta" nijedna boja nije adut
            is_trump = False
            if trump_suit:
                if trump_suit == 'all_trump':
                    is_trump = True
                elif trump_suit != 'no_trump':
                    # Pretvori trump_suit iz "spades" u "S" itd.
                    suit_map = {
                        'spades': 'S',
                        'hearts': 'H',
                        'diamonds': 'D',
                        'clubs': 'C',
                        'S': 'S',  # direktno mapiranje već radi
                        'H': 'H',
                        'D': 'D',
                        'C': 'C'
                    }
                    mapped_trump = suit_map.get(trump_suit, '')
                    is_trump = (suit == mapped_trump)
            
            if is_trump:
                return ScoringService.TRUMP_CARD_VALUES.get(value, 0)
            else:
                return ScoringService.NON_TRUMP_CARD_VALUES.get(value, 0)
                
        except Exception as e:
            logger.error(f"Greška pri izračunu vrijednosti karte: {card_code}, {trump_suit}: {e}", exc_info=True)
            return 0
    
    @staticmethod
    @track_execution_time
    def calculate_trick_points(trick_moves, trump_suit):
        """
        Izračunava ukupnu bodovnu vrijednost štiha.
        
        Args:
            trick_moves: Lista poteza u štihu
            trump_suit: Adutska boja
            
        Returns:
            int: Ukupni bodovi za štih
            
        Raises:
            ValueError: Ako trick_moves nije valjan
        """
        try:
            total = 0
            for move in trick_moves:
                if hasattr(move, 'card_code'):
                    card = move.card_code
                elif hasattr(move, 'card'):
                    card = move.card
                else:
                    logger.warning(f"Potez nema kartu: {move}")
                    continue
                    
                total += ScoringService.calculate_card_value(card, trump_suit)
            return total
            
        except Exception as e:
            logger.error(f"Greška pri izračunu bodova za štih: {e}", exc_info=True)
            return 0
    
    @staticmethod
    @track_execution_time
    @scoring_cache(timeout=300)
    def calculate_tricks_points(round_obj):
        """
        Izračunava bodove za štihove osvojene u rundi za oba tima.
        
        Args:
            round_obj: Objekt runde (Round)
            
        Returns:
            tuple: (bodovi_tim1, bodovi_tim2)
            
        Raises:
            ValueError: Ako round_obj nije valjan
        """
        try:
            if not round_obj:
                logger.error("Pokušaj izračuna bodova za štihove bez runde")
                return 0, 0
                
            game = round_obj.game
            team1_points = 0
            team2_points = 0
            
            # Dobavi sve poteze u rundi, sortirane po redoslijedu
            moves = Move.objects.filter(round=round_obj).order_by('trick_number', 'order')
            
            # Grupiraj poteze u štihove (svaki štih ima 4 poteza)
            tricks = {}
            for move in moves:
                trick_num = move.trick_number
                if trick_num not in tricks:
                    tricks[trick_num] = []
                tricks[trick_num].append(move)
            
            # Izračunaj bodove za svaki štih
            for trick_num, trick_moves in sorted(tricks.items()):
                if len(trick_moves) != 4:
                    logger.warning(f"Štih {trick_num} ima {len(trick_moves)} poteza, a trebao bi imati 4")
                    continue
                    
                # Nađi pobjednički potez
                winning_move = next((move for move in trick_moves if move.is_winning_card), None)
                if not winning_move:
                    logger.warning(f"Štih {trick_num} nema pobjednički potez")
                    continue
                
                # Izračunaj bodove za štih
                trick_points = ScoringService.calculate_trick_points(trick_moves, round_obj.trump_suit)
                
                # Dodaj dodatne bodove za zadnji štih
                if trick_num == 8:  # Zadnji štih
                    trick_points += ScoringService.LAST_TRICK_BONUS
                
                # Dodaj bodove odgovarajućem timu
                team_a_players = list(game.team_a_players.values_list('id', flat=True))
                
                if winning_move.player_id in team_a_players:
                    team1_points += trick_points
                    logger.debug(f"Tim A osvojio štih {trick_num} za {trick_points} bodova")
                else:
                    team2_points += trick_points
                    logger.debug(f"Tim B osvojio štih {trick_num} za {trick_points} bodova")
            
            # Provjeri štih-mač (štilju)
            if team1_points == 0 and team2_points > 0:
                # Tim 2 je osvojio sve štihove
                team2_points += ScoringService.CLEAN_SWEEP_BONUS
                logger.info(f"Tim B osvojio štih-mač (štilju) za dodatnih {ScoringService.CLEAN_SWEEP_BONUS} bodova")
            elif team2_points == 0 and team1_points > 0:
                # Tim 1 je osvojio sve štihove
                team1_points += ScoringService.CLEAN_SWEEP_BONUS
                logger.info(f"Tim A osvojio štih-mač (štilju) za dodatnih {ScoringService.CLEAN_SWEEP_BONUS} bodova")
            
            return team1_points, team2_points
            
        except Exception as e:
            logger.error(f"Greška pri izračunu bodova za štihove runde {round_obj.id}: {e}", exc_info=True)
            return 0, 0
    
    @staticmethod
    @track_execution_time
    def validate_declaration(declaration_type, cards, round_obj=None):
        """
        Provjerava je li zvanje valjano prema pravilima Belota.
        
        Args:
            declaration_type: Tip zvanja (jedna od ključeva u DECLARATION_VALUES)
            cards: Lista karata koje čine zvanje
            round_obj: Opcionalno, objekt runde za dodatnu validaciju
            
        Returns:
            tuple: (je_valjano, poruka_o_pogrešci)
            
        Raises:
            ValueError: Ako su parametri nevaljani
        """
        try:
            if not declaration_type or not cards:
                return False, "Nedostaju tip zvanja ili karte"
                
            # Provjeri je li tip zvanja poznat
            if declaration_type not in ScoringService.DECLARATION_VALUES:
                return False, f"Nepoznati tip zvanja: {declaration_type}"
                
            # Pretvorimo kodove karata u objekte Card
            try:
                card_objs = [Card.from_code(card) if isinstance(card, str) else card for card in cards]
            except ValueError as e:
                logger.warning(f"Nevažeći kod karte u zvanju: {e}")
                return False, f"Nevažeći kod karte: {str(e)}"
                
            # Specifične validacije za različite tipove zvanja
            if declaration_type == 'belot':
                # Provjeri je li runda definirana i ima aduta
                if round_obj and not round_obj.trump_suit:
                    return False, "Bela se može zvati samo kada postoji adut"
                
                # Provjeri ima li točno 2 karte (kralj i dama)
                if len(cards) != 2:
                    return False, "Bela mora sadržavati točno 2 karte (kralj i dama)"
                
                # Provjeri jesu li karte kralj i dama
                ranks = sorted([card.rank for card in card_objs])
                if ranks != ['K', 'Q']:
                    return False, "Bela mora sadržavati točno kralja i damu"
                
                # Provjeri jesu li obje karte iste boje
                suits = set([card.suit for card in card_objs])
                if len(suits) != 1:
                    return False, "Karte u beli moraju biti iste boje"
                
                # Provjeri je li boja adut
                suit = list(suits)[0]
                if round_obj and round_obj.trump_suit != suit:
                    return False, "Bela mora biti u adutu"
                
            elif declaration_type.startswith('four_'):
                # Zvanje 4 karte iste vrijednosti
                
                # Provjeri ima li točno 4 karte
                if len(cards) != 4:
                    return False, "Zvanje četvorke mora sadržavati točno 4 karte"
                
                # Provjeri jesu li sve karte iste vrijednosti
                ranks = set([card.rank for card in card_objs])
                if len(ranks) != 1:
                    return False, "Sve karte u zvanju četvorke moraju biti iste vrijednosti"
                
                rank = list(ranks)[0]
                # Provjeri je li vrijednost odgovara deklariranom tipu
                if declaration_type == 'four_jacks' and rank != 'J':
                    return False, "Zvanje četiri dečka mora sadržavati dečkove"
                elif declaration_type == 'four_nines' and rank != '9':
                    return False, "Zvanje četiri devetke mora sadržavati devetke"
                elif declaration_type == 'four_aces' and rank != 'A':
                    return False, "Zvanje četiri asa mora sadržavati aseve"
                elif declaration_type == 'four_tens' and rank != '10':
                    return False, "Zvanje četiri desetke mora sadržavati desetke"
                elif declaration_type == 'four_kings' and rank != 'K':
                    return False, "Zvanje četiri kralja mora sadržavati kraljeve"
                elif declaration_type == 'four_queens' and rank != 'Q':
                    return False, "Zvanje četiri dame mora sadržavati dame"
                
                # Provjeri jesu li sve boje različite (po jedna od svake)
                suits = [card.suit for card in card_objs]
                if len(set(suits)) != 4 or sorted(suits) != sorted(['S', 'H', 'D', 'C']):
                    return False, "Četvorka mora sadržavati po jednu kartu od svake boje"
                
            elif declaration_type.startswith('sequence_'):
                # Zvanje niza (terca, kvarte, kvinte...)
                
                # Parsiraj duljinu niza iz naziva
                try:
                    seq_length = int(declaration_type.split('_')[1])
                except (IndexError, ValueError):
                    return False, f"Nevaljan format zvanja niza: {declaration_type}"
                
                # Provjeri ima li točan broj karata
                if len(cards) != seq_length:
                    return False, f"Niz {seq_length} mora sadržavati točno {seq_length} karata"
                
                # Provjeri jesu li sve karte iste boje
                suits = set([card.suit for card in card_objs])
                if len(suits) != 1:
                    return False, "Sve karte u nizu moraju biti iste boje"
                
                # Provjeri je li niz valjan (uzastopne vrijednosti)
                # Sortiraj karte po vrijednosti
                sorted_cards = sorted(card_objs, key=lambda c: c.get_rank_index())
                
                # Provjeri jesu li vrijednosti u nizu
                for i in range(1, len(sorted_cards)):
                    if sorted_cards[i].get_rank_index() != sorted_cards[i-1].get_rank_index() + 1:
                        return False, "Karte u nizu moraju biti uzastopnih vrijednosti"
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Greška pri validaciji zvanja {declaration_type}: {e}", exc_info=True)
            return False, f"Greška pri validaciji zvanja: {str(e)}"
    
    @staticmethod
    @track_execution_time
    @scoring_cache(timeout=600)  # Keširanje na dulje vrijeme jer se vrijednosti zvanja ne mijenjaju
    def get_declaration_value(declaration_type, cards=None):
        """
        Vraća bodovnu vrijednost zvanja.
        
        Args:
            declaration_type: Tip zvanja
            cards: Opcionalno, lista karata za dodatnu validaciju
            
        Returns:
            int: Bodovna vrijednost zvanja
            
        Raises:
            ValueError: Ako je tip zvanja nepoznat
        """
        try:
            # Provjeri je li tip zvanja poznat
            if declaration_type not in ScoringService.DECLARATION_VALUES:
                # Posebna obrada za sequence_X gdje je X duljina niza
                if declaration_type.startswith('sequence_'):
                    try:
                        seq_length = int(declaration_type.split('_')[1])
                        if seq_length == 3:
                            return ScoringService.DECLARATION_VALUES['sequence_3']
                        elif seq_length == 4:
                            return ScoringService.DECLARATION_VALUES['sequence_4']
                        elif seq_length >= 5:
                            return ScoringService.DECLARATION_VALUES['sequence_5_plus']
                        else:
                            logger.warning(f"Nepoznata duljina niza u zvanju: {declaration_type}")
                            return 0
                    except (IndexError, ValueError):
                        logger.warning(f"Nevaljan format zvanja niza: {declaration_type}")
                        return 0
                else:
                    logger.warning(f"Nepoznati tip zvanja: {declaration_type}")
                    return 0
            
            return ScoringService.DECLARATION_VALUES[declaration_type]
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju vrijednosti zvanja {declaration_type}: {e}", exc_info=True)
            return 0
    
    @staticmethod
    @track_execution_time
    def compare_declarations(decl1, decl2):
        """
        Uspoređuje dva zvanja i određuje koje ima prednost.
        
        Args:
            decl1: Prvo zvanje (dict s ključevima 'type' i 'value')
            decl2: Drugo zvanje (dict s ključevima 'type' i 'value')
            
        Returns:
            int: 1 ako prvo zvanje ima prednost, -1 ako drugo ima prednost, 
                 0 ako su jednaka
                 
        Raises:
            ValueError: Ako su parametri nevaljani
        """
        try:
            # Provjera ulaznih parametara
            if not isinstance(decl1, dict) or not isinstance(decl2, dict):
                logger.error(f"Nevaljani parametri za usporedbu zvanja: {decl1}, {decl2}")
                return 0
            
            # Dohvati tipove i vrijednosti zvanja
            type1 = decl1.get('type', '')
            type2 = decl2.get('type', '')
            
            # Ako vrijednosti nisu eksplicitno dane, izračunaj ih
            if 'value' in decl1:
                value1 = decl1['value']
            else:
                value1 = ScoringService.get_declaration_value(type1)
                
            if 'value' in decl2:
                value2 = decl2['value']
            else:
                value2 = ScoringService.get_declaration_value(type2)
            
            # Usporedi vrijednosti
            if value1 > value2:
                return 1
            elif value1 < value2:
                return -1
            
            # Ako su vrijednosti jednake, koristi pravila prednosti
            
            # Pravilo 1: Četiri dečka ima prednost nad svim ostalima iste vrijednosti
            if type1 == 'four_jacks' and type2 != 'four_jacks':
                return 1
            elif type1 != 'four_jacks' and type2 == 'four_jacks':
                return -1
            
            # Pravilo 2: Četiri devetke imaju prednost nad svim ostalima iste vrijednosti osim četiri dečka
            if type1 == 'four_nines' and type2 != 'four_nines' and type2 != 'four_jacks':
                return 1
            elif type1 != 'four_nines' and type1 != 'four_jacks' and type2 == 'four_nines':
                return -1
            
            # Pravilo 3: Četiri asa imaju prednost nad svim ostalima iste vrijednosti osim četiri dečka i četiri devetke
            if type1 == 'four_aces' and type2 != 'four_aces' and type2 != 'four_jacks' and type2 != 'four_nines':
                return 1
            elif type1 != 'four_aces' and type1 != 'four_jacks' and type1 != 'four_nines' and type2 == 'four_aces':
                return -1
            
            # Pravilo 4: Za nizove iste vrijednosti, dulji niz ima prednost
            if type1.startswith('sequence_') and type2.startswith('sequence_'):
                try:
                    len1 = int(type1.split('_')[1])
                    len2 = int(type2.split('_')[1])
                    if len1 > len2:
                        return 1
                    elif len1 < len2:
                        return -1
                except (IndexError, ValueError):
                    pass
            
            # Ako su zvanja jednaka po svim kriterijima, smatra se da su jednaka
            return 0
            
        except Exception as e:
            logger.error(f"Greška pri usporedbi zvanja: {e}", exc_info=True)
            return 0
    
    @staticmethod
    @track_execution_time
    @scoring_cache(timeout=300)
    def calculate_declarations_points(round_obj):
        """
        Izračunava bodove za zvanja u rundi za oba tima.
        
        Args:
            round_obj: Objekt runde (Round)
            
        Returns:
            tuple: (bodovi_tim1, bodovi_tim2)
            
        Raises:
            ValueError: Ako round_obj nije valjan
        """
        try:
            if not round_obj:
                logger.error("Pokušaj izračuna bodova za zvanja bez runde")
                return 0, 0
                
            game = round_obj.game
            team1_points = 0
            team2_points = 0
            
            # Dohvati sva zvanja u rundi, sortirana po vrijednosti od najveće do najmanje
            declarations = Declaration.objects.select_related('player').filter(round=round_obj).order_by('-value')
            
            # Ako nema zvanja, vrati 0 bodova za oba tima
            if not declarations:
                return 0, 0
            
            # Grupiraj zvanja po timovima
            team_a_players = list(game.team_a_players.values_list('id', flat=True))
            
            team1_declarations = []
            team2_declarations = []
            
            for decl in declarations:
                decl_data = {
                    'id': decl.id,
                    'type': decl.declaration_type,
                    'value': decl.value,
                    'player_id': decl.player_id,
                    'player_username': decl.player.username if hasattr(decl.player, 'username') else 'Unknown',
                    'cards': decl.cards_json
                }
                
                if decl.player_id in team_a_players:
                    team1_declarations.append(decl_data)
                else:
                    team2_declarations.append(decl_data)
            
            # Ako jedan tim nema zvanja, drugi tim dobiva sve bodove
            if not team1_declarations:
                for decl in team2_declarations:
                    team2_points += decl['value']
                    
                logger.info(f"Tim B ima sva zvanja: {team2_points} bodova")
                return 0, team2_points
                
            if not team2_declarations:
                for decl in team1_declarations:
                    team1_points += decl['value']
                    
                logger.info(f"Tim A ima sva zvanja: {team1_points} bodova")
                return team1_points, 0
            
            # Sortiraj zvanja po vrijednosti i pravilima prednosti
            team1_declarations.sort(key=lambda x: (x['value'], x['type']), reverse=True)
            team2_declarations.sort(key=lambda x: (x['value'], x['type']), reverse=True)
            
            # Usporedi najviša zvanja iz svakog tima
            comparison = ScoringService.compare_declarations(team1_declarations[0], team2_declarations[0])
            
            # Ako tim 1 ima prednost ili su zvanja jednaka i tim 1 je zvao adut
            if comparison > 0 or (comparison == 0 and round_obj.calling_team == 'a'):
                for decl in team1_declarations:
                    team1_points += decl['value']
                    
                logger.info(f"Tim A ima bolja zvanja: {team1_points} bodova")
                return team1_points, 0
                
            # Ako tim 2 ima prednost ili su zvanja jednaka i tim 2 je zvao adut
            elif comparison < 0 or (comparison == 0 and round_obj.calling_team == 'b'):
                for decl in team2_declarations:
                    team2_points += decl['value']
                    
                logger.info(f"Tim B ima bolja zvanja: {team2_points} bodova")
                return 0, team2_points
                
            # Ako su zvanja jednaka i nema aduta (što se ne bi trebalo dogoditi u belotu)
            else:
                logger.warning(f"Neobična situacija: zvanja su jednaka i nema aduta u rundi {round_obj.id}")
                return 0, 0
                
        except Exception as e:
            logger.error(f"Greška pri izračunu bodova za zvanja runde {round_obj.id}: {e}", exc_info=True)
            return 0, 0
    
    @staticmethod
    def calculate_round_points(round_obj):
        """
        Izračunava ukupne bodove za rundu za oba tima, uključujući sve komponente.
        
        Args:
            round_obj: Objekt runde (Round)
            
        Returns:
            tuple: (bodovi_tim1, bodovi_tim2, pobjednički_tim)
        """
        # Izračunaj bodove za štihove
        trick_points_team1, trick_points_team2 = ScoringService.calculate_tricks_points(round_obj)
        
        # Izračunaj bodove za zvanja
        decl_points_team1, decl_points_team2 = ScoringService.calculate_declarations_points(round_obj)
        
        # Ukupni bodovi
        total_team1 = trick_points_team1 + decl_points_team1
        total_team2 = trick_points_team2 + decl_points_team2
        
        # Primijeni pravilo "prolaza"
        # Tim koji je zvao aduta mora imati više bodova od protivnika da bi "prošao"
        calling_team = round_obj.calling_team
        if calling_team == 1:
            if total_team1 <= total_team2:
                # Tim 1 nije prošao, svi bodovi idu timu 2
                total_team2 = total_team1 + total_team2
                total_team1 = 0
                winner_team = 2
            else:
                winner_team = 1
        elif calling_team == 2:
            if total_team2 <= total_team1:
                # Tim 2 nije prošao, svi bodovi idu timu 1
                total_team1 = total_team1 + total_team2
                total_team2 = 0
                winner_team = 1
            else:
                winner_team = 2
        else:
            # Ako nema zvanja aduta (što je neuobičajeno), pobjednik je tim s više bodova
            winner_team = 1 if total_team1 > total_team2 else 2
        
        return total_team1, total_team2, winner_team
    
    @staticmethod
    def check_game_winner(game):
        """
        Provjerava je li igra završena i određuje pobjednika.
        
        Args:
            game: Objekt igre (Game)
            
        Returns:
            tuple: (je_li_završeno, pobjednički_tim)
        """
        # Provjeri je li neki tim dostigao bodove potrebne za pobjedu
        if game.team1_score >= game.points_to_win:
            return True, 1
        elif game.team2_score >= game.points_to_win:
            return True, 2
        
        # Provjeri imaju li oba tima više od pola potrebnih bodova
        # U tom slučaju, pobjednik je tim s više bodova
        half_points = game.points_to_win / 2
        if game.team1_score > half_points and game.team2_score > half_points:
            if game.team1_score > game.team2_score:
                return True, 1
            elif game.team2_score > game.team1_score:
                return True, 2
        
        # Provjeri ima li zvanja "belot" koje automatski završava igru
        current_round = game.get_current_round()
        if current_round:
            belot_declaration = Declaration.objects.filter(
                round=current_round,
                type='belot'
            ).first()
            
            if belot_declaration:
                team = game.get_team_for_player(belot_declaration.player)
                return True, team
        
        return False, None

    @staticmethod
    @track_execution_time
    @scoring_cache(timeout=300)
    def calculate_card_trick_winner(moves, trump_suit=None):
        """
        Određuje pobjednika štih-a na temelju odigranih poteza.
        
        Args:
            moves: Lista poteza (Move objekti ili dict s 'card' i 'player' ključevima)
            trump_suit: Adutska boja (opcionalno)
            
        Returns:
            dict: Informacije o pobjedničkom potezu s ključevima 'move', 'player', 'card'
            
        Raises:
            ValueError: Ako nema poteza ili su potezi nevaljani
        """
        try:
            if not moves or len(moves) == 0:
                logger.error("Pokušaj određivanja pobjednika štih-a bez poteza")
                return None
                
            # Provjeri jesu li potezi u formatu objekta ili rječnika
            is_dict_format = isinstance(moves[0], dict)
            
            # Dohvati prvi potez
            first_move = moves[0]
            first_card = first_move['card'] if is_dict_format else first_move.card
            
            # Ako je prvi potez string, pretvori ga u objekt Card
            if isinstance(first_card, str):
                try:
                    first_card = Card.from_code(first_card)
                except ValueError as e:
                    logger.error(f"Nevažeći kod karte: {e}")
                    return None
            
            # Odredi boju prvog poteza
            lead_suit = first_card.suit
            
            # Inicijaliziraj pobjednički potez kao prvi potez
            winning_move = first_move
            winning_card = first_card
            
            # Prođi kroz ostale poteze i pronađi pobjednika
            for move in moves[1:]:
                current_card = move['card'] if is_dict_format else move.card
                
                # Ako je trenutni potez string, pretvori ga u objekt Card
                if isinstance(current_card, str):
                    try:
                        current_card = Card.from_code(current_card)
                    except ValueError as e:
                        logger.error(f"Nevažeći kod karte: {e}")
                        continue
                
                # Usporedi karte prema pravilima belota
                if ScoringService._is_card_stronger(current_card, winning_card, lead_suit, trump_suit):
                    winning_move = move
                    winning_card = current_card
            
            # Vrati informacije o pobjedničkom potezu
            if is_dict_format:
                return {
                    'move': winning_move,
                    'player': winning_move['player'],
                    'card': winning_card
                }
            else:
                return {
                    'move': winning_move,
                    'player': winning_move.player,
                    'card': winning_card
                }
                
        except Exception as e:
            logger.error(f"Greška pri određivanju pobjednika štih-a: {e}", exc_info=True)
            return None
    
    @staticmethod
    @track_execution_time
    def _is_card_stronger(card1, card2, lead_suit, trump_suit=None):
        """
        Uspoređuje dvije karte i određuje je li prva karta jača od druge.
        
        Args:
            card1: Prva karta (Card objekt)
            card2: Druga karta (Card objekt)
            lead_suit: Boja prvog poteza u štih-u
            trump_suit: Adutska boja (opcionalno)
            
        Returns:
            bool: True ako je prva karta jača, False inače
        """
        try:
            # Ako su obje karte aduti, usporedi ih prema vrijednosti aduta
            if trump_suit and card1.suit == trump_suit and card2.suit == trump_suit:
                return ScoringService._get_trump_card_strength(card1) > ScoringService._get_trump_card_strength(card2)
                
            # Ako je samo prva karta adut, ona je jača
            if trump_suit and card1.suit == trump_suit and card2.suit != trump_suit:
                return True
                
            # Ako je samo druga karta adut, ona je jača
            if trump_suit and card1.suit != trump_suit and card2.suit == trump_suit:
                return False
                
            # Ako nijedna karta nije adut, usporedi ih prema boji prvog poteza
            if card1.suit == lead_suit and card2.suit != lead_suit:
                return True
                
            if card1.suit != lead_suit and card2.suit == lead_suit:
                return False
                
            # Ako su obje karte iste boje (i to nije adut), usporedi ih prema vrijednosti
            if card1.suit == card2.suit:
                if card1.suit == lead_suit:
                    return ScoringService._get_card_strength(card1) > ScoringService._get_card_strength(card2)
                else:
                    # Ako nijedna karta nije boje prvog poteza niti adut, pobjeđuje prva odigrana
                    return False
                    
            # Ako su različite boje i nijedna nije adut niti boja prvog poteza, pobjeđuje prva odigrana
            return False
            
        except Exception as e:
            logger.error(f"Greška pri usporedbi karata: {e}", exc_info=True)
            return False
    
    @staticmethod
    @track_execution_time
    def _get_card_strength(card):
        """
        Vraća relativnu snagu karte u neadutskoj boji.
        
        Args:
            card: Karta (Card objekt)
            
        Returns:
            int: Relativna snaga karte (veći broj znači jača karta)
        """
        strength_map = {
            '7': 1,
            '8': 2,
            '9': 3,
            'J': 4,
            'Q': 5,
            'K': 6,
            '10': 7,
            'A': 8
        }
        return strength_map.get(card.rank, 0)
    
    @staticmethod
    @track_execution_time
    def _get_trump_card_strength(card):
        """
        Vraća relativnu snagu karte u adutskoj boji.
        
        Args:
            card: Karta (Card objekt)
            
        Returns:
            int: Relativna snaga karte u adutu (veći broj znači jača karta)
        """
        strength_map = {
            '7': 1,
            '8': 2,
            'Q': 3,
            'K': 4,
            '10': 5,
            'A': 6,
            '9': 7,
            'J': 8
        }
        return strength_map.get(card.rank, 0)
    
    @staticmethod
    @track_execution_time
    def is_valid_move(move, player_cards, trick_moves, trump_suit=None, must_follow_suit=True):
        """
        Provjerava je li potez valjan prema pravilima belota.
        
        Args:
            move: Potez koji se provjerava (karta)
            player_cards: Karte koje igrač ima u ruci
            trick_moves: Potezi već odigrani u trenutnom štih-u
            trump_suit: Adutska boja (opcionalno)
            must_follow_suit: Treba li pratiti boju (True po defaultu)
            
        Returns:
            tuple: (je_valjan, poruka_o_pogrešci)
            
        Raises:
            ValueError: Ako su parametri nevaljani
        """
        try:
            # Provjeri je li potez karta koju igrač ima
            if move not in player_cards:
                return False, "Igrač nema tu kartu u ruci"
                
            # Ako je prvi potez u štih-u, sve karte su valjane
            if not trick_moves:
                return True, ""
                
            # Dohvati boju prvog poteza
            first_card = trick_moves[0]
            if isinstance(first_card, str):
                try:
                    first_card = Card.from_code(first_card)
                except ValueError as e:
                    logger.error(f"Nevažeći kod karte: {e}")
                    return False, f"Nevažeći kod karte: {str(e)}"
            
            lead_suit = first_card.suit
            
            # Pretvori potez u objekt Card ako je string
            if isinstance(move, str):
                try:
                    move_card = Card.from_code(move)
                except ValueError as e:
                    logger.error(f"Nevažeći kod karte: {e}")
                    return False, f"Nevažeći kod karte: {str(e)}"
            else:
                move_card = move
                
            # Ako igrač prati boju, potez je valjan
            if move_card.suit == lead_suit:
                return True, ""
                
            # Ako igrač ne mora pratiti boju, potez je valjan
            if not must_follow_suit:
                return True, ""
                
            # Provjeri ima li igrač karte u boji prvog poteza
            has_lead_suit = any(
                (card.suit == lead_suit if isinstance(card, Card) else Card.from_code(card).suit == lead_suit)
                for card in player_cards
            )
            
            # Ako igrač ima karte u boji prvog poteza, mora ih igrati
            if has_lead_suit:
                return False, "Igrač mora pratiti boju prvog poteza"
                
            # Ako igrač nema karte u boji prvog poteza, može igrati bilo koju kartu
            return True, ""
            
        except Exception as e:
            logger.error(f"Greška pri provjeri valjanosti poteza: {e}", exc_info=True)
            return False, f"Greška pri provjeri valjanosti poteza: {str(e)}"
    
    @staticmethod
    @track_execution_time
    @scoring_cache(timeout=300)
    def calculate_final_score(game_obj):
        """
        Izračunava konačni rezultat igre za oba tima.
        
        Args:
            game_obj: Objekt igre (Game)
            
        Returns:
            dict: Konačni rezultat s ključevima 'team_a_score', 'team_b_score', 'winner'
            
        Raises:
            ValueError: Ako game_obj nije valjan
        """
        try:
            if not game_obj:
                logger.error("Pokušaj izračuna konačnog rezultata bez igre")
                return {
                    'team_a_score': 0,
                    'team_b_score': 0,
                    'winner': None,
                    'error': 'Igra nije pronađena'
                }
                
            # Dohvati sve runde u igri
            rounds = Round.objects.filter(game=game_obj).order_by('number')
            
            if not rounds:
                logger.warning(f"Igra {game_obj.id} nema rundi za izračun rezultata")
                return {
                    'team_a_score': 0,
                    'team_b_score': 0,
                    'winner': None,
                    'error': 'Igra nema rundi'
                }
                
            team_a_score = 0
            team_b_score = 0
            
            # Izračunaj bodove za svaku rundu
            rounds_data = []
            for round_obj in rounds:
                # Preskočimo runde koje nisu završene
                if round_obj.status != 'completed':
                    continue
                    
                # Izračunaj bodove za štihove
                team_a_tricks, team_b_tricks = ScoringService.calculate_tricks_points(round_obj)
                
                # Izračunaj bodove za zvanja
                team_a_declarations, team_b_declarations = ScoringService.calculate_declarations_points(round_obj)
                
                # Ukupni bodovi za rundu
                team_a_round_score = team_a_tricks + team_a_declarations
                team_b_round_score = team_b_tricks + team_b_declarations
                
                # Provjeri je li tim koji je zvao adut prošao
                calling_team_passed = True
                if round_obj.calling_team == 'a' and team_a_round_score <= team_b_round_score:
                    calling_team_passed = False
                elif round_obj.calling_team == 'b' and team_b_round_score <= team_a_round_score:
                    calling_team_passed = False
                
                # Izračunaj bodove za igru prema pravilima belota
                game_points = ScoringService.calculate_game_points(
                    team_a_round_score, 
                    team_b_round_score, 
                    round_obj.calling_team,
                    calling_team_passed
                )
                
                # Dodaj bodove za igru ukupnom rezultatu
                team_a_score += game_points['team_a_game_points']
                team_b_score += game_points['team_b_game_points']
                
                # Dodaj podatke o rundi
                rounds_data.append({
                    'round_number': round_obj.number,
                    'team_a_tricks': team_a_tricks,
                    'team_b_tricks': team_b_tricks,
                    'team_a_declarations': team_a_declarations,
                    'team_b_declarations': team_b_declarations,
                    'team_a_round_score': team_a_round_score,
                    'team_b_round_score': team_b_round_score,
                    'calling_team': round_obj.calling_team,
                    'calling_team_passed': calling_team_passed,
                    'team_a_game_points': game_points['team_a_game_points'],
                    'team_b_game_points': game_points['team_b_game_points']
                })
                
            # Odredi pobjednika
            winner = None
            if team_a_score > team_b_score:
                winner = 'a'
            elif team_b_score > team_a_score:
                winner = 'b'
            else:
                winner = 'tie'
                
            logger.info(f"Konačni rezultat igre {game_obj.id}: Tim A {team_a_score} - Tim B {team_b_score}, pobjednik: {winner}")
                
            return {
                'team_a_score': team_a_score,
                'team_b_score': team_b_score,
                'winner': winner,
                'rounds': rounds_data
            }
            
        except Exception as e:
            logger.error(f"Greška pri izračunu konačnog rezultata igre {game_obj.id}: {e}", exc_info=True)
            return {
                'team_a_score': 0,
                'team_b_score': 0,
                'winner': None,
                'error': str(e)
            }
    
    @staticmethod
    @track_execution_time
    @scoring_cache(timeout=600)  # Dulje keširanje jer se pravila bodovanja ne mijenjaju
    def calculate_game_points(team_a_score, team_b_score, calling_team, calling_team_passed):
        """
        Izračunava bodove za igru prema pravilima belota.
        
        Args:
            team_a_score: Bodovi tima A u rundi
            team_b_score: Bodovi tima B u rundi
            calling_team: Tim koji je zvao adut ('a' ili 'b')
            calling_team_passed: Je li tim koji je zvao adut prošao
            
        Returns:
            dict: Bodovi za igru s ključevima 'team_a_game_points', 'team_b_game_points'
            
        Raises:
            ValueError: Ako su parametri nevaljani
        """
        try:
            team_a_game_points = 0
            team_b_game_points = 0
            
            # Provjeri je li tim koji je zvao adut prošao
            if not calling_team_passed:
                # Tim koji je zvao adut nije prošao - protivnički tim dobiva sve bodove
                if calling_team == 'a':
                    team_b_game_points = 3  # Tim B dobiva 3 boda (štiha)
                    logger.info(f"Tim A nije prošao, Tim B dobiva 3 boda")
                else:
                    team_a_game_points = 3  # Tim A dobiva 3 boda (štiha)
                    logger.info(f"Tim B nije prošao, Tim A dobiva 3 boda")
            else:
                # Tim koji je zvao adut je prošao - bodovi se računaju prema razlici
                total_score = team_a_score + team_b_score
                
                if calling_team == 'a':
                    # Tim A je zvao adut i prošao
                    if team_a_score == total_score:
                        # Tim A je uzeo sve štihove (čista pobjeda)
                        team_a_game_points = 3
                        logger.info(f"Tim A je uzeo sve štihove, dobiva 3 boda")
                    elif team_a_score >= 3 * total_score / 4:
                        # Tim A je uzeo 3/4 ili više bodova
                        team_a_game_points = 2
                        logger.info(f"Tim A je uzeo 3/4 ili više bodova, dobiva 2 boda")
                    else:
                        # Tim A je uzeo manje od 3/4 bodova
                        team_a_game_points = 1
                        team_b_game_points = 1
                        logger.info(f"Tim A je prošao, ali uzeo manje od 3/4 bodova, oba tima dobivaju po 1 bod")
                else:
                    # Tim B je zvao adut i prošao
                    if team_b_score == total_score:
                        # Tim B je uzeo sve štihove (čista pobjeda)
                        team_b_game_points = 3
                        logger.info(f"Tim B je uzeo sve štihove, dobiva 3 boda")
                    elif team_b_score >= 3 * total_score / 4:
                        # Tim B je uzeo 3/4 ili više bodova
                        team_b_game_points = 2
                        logger.info(f"Tim B je uzeo 3/4 ili više bodova, dobiva 2 boda")
                    else:
                        # Tim B je uzeo manje od 3/4 bodova
                        team_a_game_points = 1
                        team_b_game_points = 1
                        logger.info(f"Tim B je prošao, ali uzeo manje od 3/4 bodova, oba tima dobivaju po 1 bod")
            
            return {
                'team_a_game_points': team_a_game_points,
                'team_b_game_points': team_b_game_points
            }
            
        except Exception as e:
            logger.error(f"Greška pri izračunu bodova za igru: {e}", exc_info=True)
            return {
                'team_a_game_points': 0,
                'team_b_game_points': 0,
                'error': str(e)
            }
    
    @staticmethod
    @track_execution_time
    def get_player_statistics(user_id):
        """
        Dohvaća statistiku igrača.
        
        Args:
            user_id: ID korisnika
            
        Returns:
            dict: Statistika igrača s ključevima 'games_played', 'games_won', 'win_rate', itd.
            
        Raises:
            ValueError: Ako user_id nije valjan
        """
        try:
            from game.models import Game, GamePlayer
            from django.db.models import Count, Q, F, Sum, Avg
            
            if not user_id:
                logger.error("Pokušaj dohvaćanja statistike bez ID-a korisnika")
                return {
                    'error': 'Korisnik nije pronađen'
                }
                
            # Dohvati sve igre u kojima je korisnik sudjelovao
            player_games = GamePlayer.objects.filter(user_id=user_id, is_active=True)
            
            # Ukupan broj odigranih igara
            games_played = player_games.count()
            
            if games_played == 0:
                return {
                    'games_played': 0,
                    'games_won': 0,
                    'games_lost': 0,
                    'win_rate': 0,
                    'total_points': 0,
                    'avg_points_per_game': 0,
                    'best_score': 0,
                    'worst_score': 0,
                    'total_declarations': 0,
                    'avg_declarations_per_game': 0
                }
                
            # Broj pobjeda
            games_won = player_games.filter(
                Q(team='a', game__winner='a') | 
                Q(team='b', game__winner='b')
            ).count()
            
            # Broj poraza
            games_lost = player_games.filter(
                Q(team='a', game__winner='b') | 
                Q(team='b', game__winner='a')
            ).count()
            
            # Postotak pobjeda
            win_rate = (games_won / games_played) * 100 if games_played > 0 else 0
            
            # Ukupan broj bodova
            total_points = player_games.aggregate(
                total=Sum(
                    Case(
                        When(team='a', then=F('game__team_a_score')),
                        When(team='b', then=F('game__team_b_score')),
                        default=0,
                        output_field=models.IntegerField()
                    )
                )
            )['total'] or 0
            
            # Prosječan broj bodova po igri
            avg_points_per_game = total_points / games_played if games_played > 0 else 0
            
            # Najbolji rezultat
            best_score = player_games.aggregate(
                best=Max(
                    Case(
                        When(team='a', then=F('game__team_a_score')),
                        When(team='b', then=F('game__team_b_score')),
                        default=0,
                        output_field=models.IntegerField()
                    )
                )
            )['best'] or 0
            
            # Najgori rezultat
            worst_score = player_games.aggregate(
                worst=Min(
                    Case(
                        When(team='a', then=F('game__team_a_score')),
                        When(team='b', then=F('game__team_b_score')),
                        default=0,
                        output_field=models.IntegerField()
                    )
                )
            )['worst'] or 0
            
            # Ukupan broj zvanja
            from game.models import Declaration
            total_declarations = Declaration.objects.filter(player_id=user_id).count()
            
            # Prosječan broj zvanja po igri
            avg_declarations_per_game = total_declarations / games_played if games_played > 0 else 0
            
            return {
                'games_played': games_played,
                'games_won': games_won,
                'games_lost': games_lost,
                'win_rate': round(win_rate, 2),
                'total_points': total_points,
                'avg_points_per_game': round(avg_points_per_game, 2),
                'best_score': best_score,
                'worst_score': worst_score,
                'total_declarations': total_declarations,
                'avg_declarations_per_game': round(avg_declarations_per_game, 2)
            }
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju statistike igrača {user_id}: {e}", exc_info=True)
            return {
                'error': str(e)
            }